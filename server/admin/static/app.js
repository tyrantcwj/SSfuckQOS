(() => {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.dataset.tab;
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panels.forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
    });
  });

  const btn = document.getElementById("btn-lan-check");
  const out = document.getElementById("lan-result");
  if (btn && out) {
    btn.addEventListener("click", async () => {
      out.classList.remove("hidden");
      out.textContent = "探测中…";
      try {
        const res = await fetch("/api/lan-check");
        const data = await res.json();
        if (!data.ok) {
          out.textContent = data.error || "探测失败";
          return;
        }
        const lines = [
          `LAN CIDRs: ${data.lan_cidrs.join(", ")}`,
          ...data.probes.map(
            (p) => `${p.reachable ? "OK " : "FAIL"}  ${p.ip}`
          ),
          "",
          "说明：探测的是网段内常见网关地址（如 x.x.x.1）。",
          "若服务端用 bridge 网络导致探测失败，请改用 network_mode: host。",
        ];
        out.textContent = lines.join("\n");
      } catch (err) {
        out.textContent = String(err);
      }
    });
  }
})();
