// Small formatting helpers shared by the components.

export function duration(seconds) {
  if (seconds == null || seconds < 0 || Number.isNaN(seconds)) return "—";
  let rest = Math.floor(seconds);
  const days = Math.floor(rest / 86400);
  rest -= days * 86400;
  const pad = (value) => String(value).padStart(2, "0");
  const clock = `${pad(Math.floor(rest / 3600))}:${pad(Math.floor((rest % 3600) / 60))}:${pad(rest % 60)}`;
  return days ? `${days} d ${clock}` : clock;
}

export function number(value, language, digits = 0) {
  return Number(value).toLocaleString(language === "pl" ? "pl-PL" : "en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// copy text also over plain http on the LAN, where the browser has no clipboard API
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.append(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}
