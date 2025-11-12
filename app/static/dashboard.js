const BASE_URL = "http://127.0.0.1:8000";
let token = localStorage.getItem("token");
let user = null;
let chartInstance = null;

document.addEventListener("DOMContentLoaded", async () => {
  if (token) await showDashboard();
});

async function signup() {
  const email = emailEl().value;
  const password = passEl().value;
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  alert(res.ok ? "✅ Signup successful! Please login." : "❌ Signup failed");
}

async function login() {
  const email = emailEl().value;
  const password = passEl().value;
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (res.ok && data.access_token) {
    token = data.access_token;
    localStorage.setItem("token", token);
    await showDashboard();
  } else alert("❌ " + (data.detail || "Login failed"));
}

async function showDashboard() {
  const res = await fetch(`${BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  user = await res.json();
  if (!res.ok) return logout();

  document.getElementById("authCard").style.display = "none";
  document.getElementById("dashboard").style.display = "block";
  document.getElementById("userEmail").innerText = user.email;
  document.getElementById("userRole").innerText = user.role;
  document.getElementById("adminPanel").style.display =
    user.role === "admin" ? "block" : "none";

  await loadDocuments();
}

function logout() {
  localStorage.removeItem("token");
  location.reload();
}

function emailEl() {
  return document.getElementById("email");
}
function passEl() {
  return document.getElementById("password");
}

async function uploadFile() {
  const fileInput = document.getElementById("fileInput");
  const runOCR = document.getElementById("runOCR").checked;
  const primaryTag = document.getElementById("primaryTag").value.trim();
  const secondaryTags = document.getElementById("secondaryTags").value.trim();
  const uploadStatus = document.getElementById("uploadStatus");

  if (!fileInput.files.length) return alert("Please select a file first.");
  uploadStatus.innerText = "⏳ Uploading...";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  if (!runOCR) {
    formData.append("primaryTag", primaryTag);
    if (secondaryTags) formData.append("secondaryTags", secondaryTags);
  }

  const endpoint = runOCR
    ? "/v1/docs/ocr-scan"
    : `/v1/docs?primaryTag=${encodeURIComponent(
        primaryTag
      )}&secondaryTags=${encodeURIComponent(secondaryTags)}`;

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  const data = await res.json();
  if (res.ok) {
    uploadStatus.innerText = runOCR
      ? `✅ OCR processed (${data.classification})`
      : "✅ Uploaded successfully";
    await loadDocuments();
  } else {
    uploadStatus.innerText = `❌ ${data.detail || "Upload failed"}`;
  }
}

async function loadDocuments() {
  const res = await fetch(`${BASE_URL}/v1/docs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const tbody = document.querySelector("#docTable tbody");
  tbody.innerHTML = "";

  if (!res.ok) {
    tbody.innerHTML = `<tr><td colspan="5">❌ Failed to load documents</td></tr>`;
    return;
  }

  const docs = await res.json();
  if (!docs.length) {
    tbody.innerHTML = `<tr><td colspan="5">📭 No documents found</td></tr>`;
    return;
  }

  docs.forEach((d) => {
    const created = new Date(d.createdAt).toLocaleString();
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${d.filename}</td>
      <td>${d.mime}</td>
      <td>${(d.tags || []).join(", ") || "-"}</td>
      <td>${created}</td>
      <td><button onclick="downloadDoc('${d._id}')">📥 Download</button></td>
    `;
    tbody.appendChild(tr);
  });
}

async function downloadDoc(id) {
  try {
    const res = await fetch(`${BASE_URL}/v1/docs/${id}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const err = await res.json();
      alert("❌ " + (err.detail || "Download failed"));
      return;
    }

    const blob = await res.blob();
    const filename =
      res.headers
        .get("content-disposition")
        ?.split("filename=")[1]
        ?.replace(/"/g, "") || "download.bin";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    console.error(err);
    alert("❌ Download failed");
  }
}

async function fetchMetrics() {
  const res = await fetch(`${BASE_URL}/v1/actions/usage/month`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  const credits = data.total_credits || 0;
  const ctx = document.getElementById("usageChart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Credits Used (This Month)"],
      datasets: [
        { label: "Credits", data: [credits], backgroundColor: "#2563eb" },
      ],
    },
  });
}
async function downloadFile(url, filename) {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return alert("❌ Failed to download file");

  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function runActions() {
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
  const res = await fetch(`${BASE_URL}/v1/actions/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok) {
    document.getElementById("resultStatus").innerText = `❌ ${
      data.detail || "Failed"
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
 if (data.downloads?.text) {
   const btn = document.createElement("button");
   btn.textContent = "⬇ Download Text";
   btn.onclick = () => downloadFile(data.downloads.text, "summary.txt");
   document.getElementById("resultStatus").appendChild(btn);
 }

 if (data.downloads?.csv) {
   const btn = document.createElement("button");
   btn.textContent = "⬇ Download CSV";
   btn.onclick = () => downloadFile(data.downloads.csv, "report.csv");
   document.getElementById("resultStatus").appendChild(btn);
 }


}

