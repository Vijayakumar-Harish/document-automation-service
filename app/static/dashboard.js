const BASE_URL = "http://127.0.0.1:8000";
let token = localStorage.getItem("token");
let user = null;
let chartInstance = null;

const ROLE_PERMISSIONS = {
  admin: {
    canUpload: true,
    canRunAI: true,
    canViewMetrics: true,
    canViewDocs: true,
    canManageUsers: true,
  },
  support: {
    canUpload: false,
    canRunAI: false,
    canViewMetrics: true,
    canViewDocs: true,
    canManageUsers: true,
  },
  user: {
    canUpload: true,
    canRunAI: true,
    canViewMetrics: false,
    canViewDocs: true,
    canManageUsers: false,
  },
};
function can(permission) {
  if (!user || !user.role) return false;
  return !!ROLE_PERMISSIONS[user.role]?.[permission];
}


document.addEventListener("DOMContentLoaded", async () => {

  if (token) {
    await showDashboard();
  } else {

    document.getElementById("authCard")?.classList?.remove?.("hidden");
  }
});


async function signup() {
  const email = (document.getElementById("email") || {}).value;
  const password = (document.getElementById("password") || {}).value;
  setAuthStatus("Signing up…");

  try {
    const res = await fetch(`${BASE_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await safeJson(res);
    if (!res.ok) {
      const message = extractErrorMessage(data, res.statusText);
      setAuthStatus(`❌ Signup failed: ${message}`);
      return;
    }

    setAuthStatus("✅ Signup successful — please login.");
  } catch (err) {
    console.error("signup error", err);
    setAuthStatus("❌ Signup error — check console.");
  }
}
function extractErrorMessage(data, fallback = "Request failed") {
  if (!data) return fallback;
  if (Array.isArray(data.detail)) {

    return data.detail
      .map((e) => `${e.msg} (${e.loc?.join(" → ")})`)
      .join(", ");
  }
  if (typeof data.detail === "string") return data.detail;
  if (typeof data === "string") return data;
  if (data.message) return data.message;
  if (data.error) return data.error;
  return fallback;
}

async function login() {
  const email = (document.getElementById("email") || {}).value;
  const password = (document.getElementById("password") || {}).value;
  setAuthStatus("Logging in…");

  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await safeJson(res);

    if (!res.ok) {
      const message = extractErrorMessage(data, res.statusText);
      setAuthStatus(`❌ Login failed: ${message}`);
      return;
    }

    if (!data?.access_token) {
      setAuthStatus("❌ Login returned no token (check server).");
      console.error("login response", data);
      return;
    }

    token = data.access_token;
    localStorage.setItem("token", token);
    setAuthStatus("✅ Logged in");
    await showDashboard();
  } catch (err) {
    console.error("login error", err);
    setAuthStatus("❌ Login error — check console.");
  }
}

function logout() {
  localStorage.removeItem("token");
  token = null;
  user = null;

  window.location.reload();
}

function setAuthStatus(msg) {
  const s = document.getElementById("authStatus");
  if (s) s.innerText = msg;
}


function emailEl() {
  return document.getElementById("email");
}
function passEl() {
  return document.getElementById("password");
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch (e) {
    return { status: res.status, statusText: res.statusText };
  }
}


async function showDashboard() {

  if (!token) {
    return;
  }

  try {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      console.warn("/auth/me returned", res.status);
  
      localStorage.removeItem("token");
      token = null;
      setAuthStatus("Session invalid — please login again.");
      return;
    }

    user = await res.json();


    document.getElementById("authCard")?.classList?.add?.("hidden");
    document.getElementById("dashboard")?.classList?.remove?.("hidden");

    document.getElementById("userEmail").innerText =
      user.email || user.sub || "me";
    document.getElementById("userRole").innerText = user.role || "user";
 
    if (user.role === "admin") {
      document.getElementById("adminPanel")?.classList?.remove?.("hidden");
      await loadAllUsers();
    } else {
      document.getElementById("adminPanel")?.classList?.add?.("hidden");
    }

    await loadDocuments();
    await loadFolders();
    await loadUsage();
  } catch (err) {
    console.error("showDashboard error", err);
    setAuthStatus("❌ Failed to validate session — check console.");
  }
}


async function uploadFile() {
  if (!can("canUpload"))
    return alert("🚫 You don’t have permission to upload.");
  const fileInput = document.getElementById("fileInput");
  const runOCR = document.getElementById("runOCR")?.checked;
  const primaryTag = document.getElementById("primaryTag")?.value?.trim() || "";
  const secondaryTags =
    document.getElementById("secondaryTags")?.value?.trim() || "";
  const uploadStatus = document.getElementById("uploadStatus");

  if (!fileInput?.files?.length) {
    return alert("Please select a file first.");
  }
  if (!token) {
    return alert("Not authenticated. Please login.");
  }

  uploadStatus.innerText = "⏳ Uploading…";
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);


  if (runOCR) {
    if (primaryTag) formData.append("primaryTag", primaryTag);
    if (secondaryTags) formData.append("secondaryTags", secondaryTags);

    try {
      const res = await fetch(`${BASE_URL}/v1/docs/ocr-scan`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }, // DO NOT set Content-Type with FormData
        body: formData,
      });
      const data = await safeJson(res);
      if (!res.ok) {
        let message = "Upload failed";
  if (Array.isArray(data?.detail)) {
    message = data.detail.map(e => `${e.msg} (${e.loc?.join(" → ")})`).join(", ");
  } else if (typeof data?.detail === "string") {
    message = data.detail;
  }
  uploadStatus.innerText = `❌ ${message}`;
  console.warn("Upload error", data);
  return;
      }
      uploadStatus.innerText = `✅ OCR processed (${
        data.classification || "ok"
      })`;
      await loadDocuments();
      await loadFolders();
    } catch (err) {
      console.error("ocr upload error", err);
      uploadStatus.innerText = "❌ Upload error — see console";
    }
  } else {
    const url = `${BASE_URL}/v1/docs?primaryTag=${encodeURIComponent(
      primaryTag || ""
    )}&secondaryTags=${encodeURIComponent(secondaryTags || "")}`;
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }, // don't set Content-Type
        body: formData,
      });
      const data = await safeJson(res);
      if (!res.ok) {
        let message = "Upload failed";
        if (Array.isArray(data?.detail)) {
          message = data.detail
            .map((e) => `${e.msg} (${e.loc?.join(" → ")})`)
            .join(", ");
        } else if (typeof data?.detail === "string") {
          message = data.detail;
        }
        uploadStatus.innerText = `❌ ${message}`;
        console.warn("Upload error", data);
        return;
      }
      uploadStatus.innerText = `✅ Uploaded successfully`;
      await loadDocuments();
      await loadFolders();
    } catch (err) {
      console.error("upload error", err);
      uploadStatus.innerText = "❌ Upload error — see console";
    }
  }
}


async function loadDocuments() {
  if (!token) return;
  const tbody = document.querySelector("#docTable tbody");
  tbody.innerHTML = `<tr><td colspan="5">⏳ Loading…</td></tr>`;

  try {
    const res = await fetch(`${BASE_URL}/v1/docs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = await safeJson(res);
      tbody.innerHTML = `<tr><td colspan="5">❌ Failed to load documents: ${
        err?.detail || res.status
      }</td></tr>`;
      console.warn("/v1/docs failed", err);
      return;
    }
    const docs = await res.json();
    if (!Array.isArray(docs) || docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">📭 No documents found</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    docs.forEach((d) => {
      const created = d.createdAt
        ? new Date(d.createdAt).toLocaleString()
        : "-";
      const tags = d.tags || d.tagNames || (d._tags ? d._tags.join(", ") : []);
      const id = d._id || d.id || d.id_str || d.id;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d.filename || "-")}</td>
        <td>${escapeHtml(d.mime || "-")}</td>
        <td>${escapeHtml(
          Array.isArray(tags) ? tags.join(", ") : tags || "-"
        )}</td>
        <td>${escapeHtml(created)}</td>
        <td><button class="btn btn-light small" onclick="downloadDoc('${id}')">📥 Download</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("loadDocuments error", err);
    tbody.innerHTML = `<tr><td colspan="5">❌ Error loading documents (see console)</td></tr>`;
  }
}

async function loadFolders() {
  if (!token) return;
  const tbody = document.querySelector("#folderTable tbody");
  tbody.innerHTML = `<tr><td colspan="3">⏳ Loading…</td></tr>`;
  try {
    const res = await fetch(`${BASE_URL}/v1/folders`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = await safeJson(res);
      tbody.innerHTML = `<tr><td colspan="3">❌ Failed to load folders: ${
        err?.detail || res.status
      }</td></tr>`;
      return;
    }
    const data = await res.json();
    tbody.innerHTML = "";
    data.forEach((f) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(f.name)}</td>
        <td>${escapeHtml(String(f.count || 0))}</td>
        <td><button class="btn btn-light small" onclick="loadFolderDocs('${escapeJsString(
          f.name
        )}')">📂 View</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("loadFolders error", err);
    tbody.innerHTML = `<tr><td colspan="3">❌ Error loading folders (see console)</td></tr>`;
  }
}

async function loadFolderDocs(tagName) {
  if (!token) return;
  try {
    const res = await fetch(
      `${BASE_URL}/v1/folders/${encodeURIComponent(tagName)}/docs`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!res.ok) {
      const err = await safeJson(res);
      alert("Failed to load folder docs: " + (err?.detail || res.status));
      return;
    }
    const docs = await res.json();
    const tbody = document.querySelector("#docTable tbody");
    tbody.innerHTML = "";
    docs.forEach((d) => {
      const created = d.createdAt
        ? new Date(d.createdAt).toLocaleString()
        : "-";
      const id = d._id || d.id;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d.filename || "-")}</td>
        <td>${escapeHtml(d.mime || "-")}</td>
        <td>${escapeHtml(
          (d.tags || []).join ? d.tags.join(", ") : d.tags || "-"
        )}</td>
        <td>${escapeHtml(created)}</td>
        <td><button class="btn btn-light small" onclick="downloadDoc('${id}')">📥 Download</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("loadFolderDocs error", err);
    alert("Error loading folder docs (see console)");
  }
}


async function downloadDoc(id) {
  if (!token) return alert("Not authenticated");
  try {
    const res = await fetch(`${BASE_URL}/v1/docs/${id}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = await safeJson(res);
      alert("❌ " + (err.detail || "Download failed"));
      return;
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    let fname = "download.bin";
    const m = disposition.match(/filename="?(.+?)"?$/);
    if (m) fname = m[1];
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fname;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    console.error("downloadDoc error", err);
    alert("❌ Download error — see console");
  }
}

async function runActions() {
  if (!can("canRunAI"))
    return alert("🚫 You don’t have permission to run AI actions.");
  if (!token) return alert("Not authenticated");
  const type = document.getElementById("scopeType").value;
  const name = document.getElementById("scopeName").value.trim();
  const makeDoc = document.getElementById("makeDoc").checked;
  const makeCsv = document.getElementById("makeCsv").checked;
  const prompt =
    document.getElementById("prompt").value.trim() ||
    "Summarize the documents and generate CSV if needed.";

  const payload = {
    scope: { type, name },
    messages: [{ role: "user", content: prompt }],
    actions: [],
  };
  if (makeDoc) payload.actions.push("make_document");
  if (makeCsv) payload.actions.push("make_csv");

  document.getElementById("resultStatus").innerText = "⏳ Running AI task...";
  try {
    const res = await fetch(`${BASE_URL}/v1/actions/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await safeJson(res);
    if (!res.ok) {
      document.getElementById("resultStatus").innerText = `❌ ${
        data?.detail || res.status
      }`;
      return;
    }
    document.getElementById(
      "resultStatus"
    ).innerText = `✅ Completed (Credits used: ${data.credits_used})`;
    document.getElementById("outputText").innerText = JSON.stringify(
      data,
      null,
      2
    );


    const resultArea = document.getElementById("resultStatus");

    const oldBtns = resultArea.querySelectorAll(".download-btn");
    oldBtns.forEach((b) => b.remove());

    if (data.downloads?.text) {
      const btn = document.createElement("button");
      btn.className = "btn btn-light small download-btn";
      btn.textContent = "⬇ Download Text";
      btn.onclick = () => downloadFile(data.downloads.text, "summary.txt");
      resultArea.appendChild(btn);
    }
    if (data.downloads?.csv) {
      const btn = document.createElement("button");
      btn.className = "btn btn-light small download-btn";
      btn.textContent = "⬇ Download CSV";
      btn.onclick = () => downloadFile(data.downloads.csv, "report.csv");
      resultArea.appendChild(btn);
    }

    await loadDocuments();
    await loadFolders();
    await loadUsage();
  } catch (err) {
    console.error("runActions error", err);
    document.getElementById("resultStatus").innerText =
      "❌ AI task failed — see console.";
  }
}

async function downloadFile(url, filename) {

  if (!token) return alert("Not authenticated");
  try {
    const full = url.startsWith("http") ? url : `${BASE_URL}${url}`;
    const res = await fetch(full, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = await safeJson(res);
      return alert("❌ Download failed: " + (err?.detail || res.status));
    }
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    console.error("downloadFile error", err);
    alert("❌ Download error — see console");
  }
}


async function loadAllUsers() {
  if (!can("canManageUsers")) return;
  const tbody = document.querySelector("#userTable tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="4">⏳ Loading...</td></tr>`;

  try {
    const res = await fetch(`${BASE_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await safeJson(res);
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="4">❌ Failed to load users</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    for (const u of data) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(u.email)}</td>
        <td>
          <select onchange="setUserRole('${u.id}', this.value)">
            ${["user", "support", "admin"]
              .map(
                (r) =>
                  `<option value="${r}" ${
                    r === u.role ? "selected" : ""
                  }>${r}</option>`
              )
              .join("")}
          </select>
        </td>
        <td id="credits-${u.id}">...</td>
        <td><button class="btn small" onclick="loadUserCredits('${
          u.id
        }')">🔍 View Usage</button></td>
      `;
      tbody.appendChild(tr);
      loadUserCredits(u.id).catch(() => {});
    }
  } catch (err) {
    console.error("loadAllUsers error", err);
    tbody.innerHTML = `<tr><td colspan="4">❌ Error loading users (see console)</td></tr>`;
  }
}

async function setUserRole(userId, newRole) {
  if (!can("canManageUsers")) return alert("🚫 No permission");
  try {
    const res = await fetch(
      `${BASE_URL}/admin/users/${userId}/role?new_role=${encodeURIComponent(
        newRole
      )}`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const data = await safeJson(res);
    if (!res.ok) {
      alert("❌ " + (data.detail || res.status));
    } else {
      alert("✅ " + (data.message || "Role updated"));

      await loadAllUsers();
    }
  } catch (err) {
    console.error("setUserRole error", err);
    alert("❌ Error updating role (see console)");
  }
}

async function loadUserCredits(userId) {
  try {
    const res = await fetch(`${BASE_URL}/v1/actions/usage/${userId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await safeJson(res);
    const td = document.getElementById(`credits-${userId}`);
    if (td) td.innerText = res.ok ? data.total_credits || 0 : "-";
  } catch (err) {
    console.error("loadUserCredits error", err);
    const td = document.getElementById(`credits-${userId}`);
    if (td) td.innerText = "-";
  }
}


function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
function escapeJsString(s) {
  return (s || "").replace(/'/g, "\\'").replace(/"/g, '\\"');
}

(function () {
  const btn = document.getElementById("darkToggle");
  const body = document.body;

  function setIcon(isDark) {
    if (!btn) return;
    btn.textContent = isDark ? "☀️" : "🌙";
    btn.title = isDark ? "Switch to light mode" : "Switch to dark mode";
  }


  const saved = localStorage.getItem("documentai_theme");
  const prefersDark =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const startDark = saved ? saved === "dark" : prefersDark;

  if (startDark) {
    body.classList.add("dark-mode");
    setIcon(true);
  } else {
    body.classList.remove("dark-mode");
    setIcon(false);
  }

  if (btn) {
    btn.addEventListener("click", () => {
      const isDark = body.classList.toggle("dark-mode");
      localStorage.setItem("documentai_theme", isDark ? "dark" : "light");
      setIcon(isDark);
    });
  }
})();

async function loadUsage() {
  if (!token) return;
  try {
    const res = await fetch(`${BASE_URL}/v1/actions/usage`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("creditsUsed").innerText = data.used;
    document.getElementById("creditsLimit").innerText = data.limit;
  } catch (err) {
    console.error("loadUsage error", err);
  }
}

async function searchDocs() {
  const q = document.getElementById("searchInput").value.trim();
  const scope = document.getElementById("searchScope").value;
  if (!q) return alert("Please enter a search query");

  const tbody = document.querySelector("#docTable tbody");
  tbody.innerHTML = `<tr><td colspan="5">🔍 Searching...</td></tr>`;

  try {
    const url = `${BASE_URL}/v1/docs/search?q=${encodeURIComponent(q)}${
      scope ? `&scope=${scope}` : ""
    }`;
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();

    if (!Array.isArray(data) || !data.length) {
      tbody.innerHTML = `<tr><td colspan="5">📭 No results found</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    data.forEach((d) => {
      const created = d.createdAt
        ? new Date(d.createdAt).toLocaleString()
        : "-";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d.filename || "-")}</td>
        <td>${escapeHtml(d.mime || "-")}</td>
        <td>${escapeHtml((d.tags || []).join(", "))}</td>
        <td>${escapeHtml(created)}</td>
        <td><button class="btn btn-light small" onclick="downloadDoc('${
          d.id
        }')">📥 Download</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("searchDocs error", err);
    tbody.innerHTML = `<tr><td colspan="5">❌ Error during search</td></tr>`;
  }
}
