export const $ = (s) => document.querySelector(s);
export const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export async function api(path, method = "GET", body) {
  const res = await fetch("/api" + path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
let timer;
export function toast(message, error = false) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  el.style.borderLeftColor = error ? "var(--bad)" : "var(--accent)";
  clearTimeout(timer);
  timer = setTimeout(() => (el.hidden = true), 6000);
}
export const money = (cents, currency = "NGN") =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(cents / 100);
export const stat = (label, value, note = "") =>
  `<div class="stat"><label>${esc(label)}</label><strong>${esc(value)}</strong><span>${esc(note)}</span></div>`;
export const empty = (message) => `<div class="empty">${esc(message)}</div>`;
export function download(path) {
  const a = document.createElement("a");
  a.href = "/api" + path;
  document.body.append(a);
  a.click();
  a.remove();
}
export async function action(fn) {
  try {
    await fn();
  } catch (error) {
    toast(error.message, true);
  }
}
export function formData(form) {
  return Object.fromEntries(new FormData(form));
}
$("#date").textContent = new Date().toLocaleDateString("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
document.addEventListener("click", (event) => {
  if (event.target.matches("[data-close]"))
    event.target.closest("dialog").close();
});
