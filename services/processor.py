from typing import List

def mock_process(messages: List[dict], action: str, context: dict) -> dict:
    file_list = ",".join([d.get("filename","") for d in context.get("documents", [])])
    prompt = " ".join([m.get("content", "") for m in messages])[:200]
    if action == "make_document":
        text = f"Generated document from: {file_list}\nPrompt: {prompt}"
        return {"mime":"text/plain","text":text,"filename":"generated.txt"}
    if action == "make_csv":
        rows = ["vendor,total"]
        for idx, d in enumerate(context.get("documents", []), start=1):
            vendor = (d.get("filename") or f"vendor{idx}")[:20].replace(",","_")
            rows.append(f"{vendor},{idx*100}")
        csv = "\n".join(rows)
        return {"mime":"text/csv","text":csv, "filename":"vendor_totals.csv"}
    return {}
