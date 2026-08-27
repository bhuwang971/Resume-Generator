from __future__ import annotations

import base64
import hashlib
import html

import streamlit.components.v1 as components


def render_copy_button(text: str, label: str, key: str) -> None:
    encoded = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
    element_id = "copy-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    safe_label = html.escape(label, quote=True)
    components.html(
        f"""<!doctype html><html><body style="margin:0;font-family:system-ui,sans-serif">
        <button id="{element_id}" type="button">{safe_label}</button>
        <span id="status-{element_id}" role="status"></span>
        <script>(() => {{
          const button=document.getElementById("{element_id}");
          const status=document.getElementById("status-{element_id}");
          button.addEventListener("click", async () => {{
            try {{
              const bytes=Uint8Array.from(atob("{encoded}"), c => c.charCodeAt(0));
              await navigator.clipboard.writeText(new TextDecoder("utf-8").decode(bytes));
              status.textContent=" Copied.";
            }} catch (_) {{ status.textContent=" Copy failed; select the text and press Ctrl+C."; }}
          }});
        }})();</script></body></html>""",
        height=42,
        scrolling=False,
    )
