/** The API's upload rules, checked here first so a wrong file fails without an upload. */

export const ACCEPTED_EXTENSIONS = [".txt", ".md", ".markdown", ".html", ".htm", ".pdf"] as const;
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot <= 0 ? "" : name.slice(dot).toLowerCase();
}

/** Why a file cannot be uploaded, or null when it can. */
export function rejectionReason(file: { name: string; size: number }): string | null {
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(fileExtension(file.name))) {
    return "This file type is not supported. Use .txt, .md, .html or .pdf.";
  }
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) return "The file is larger than the 25 MB limit.";
  return null;
}
