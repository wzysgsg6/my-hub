#!/usr/bin/env python3
"""Assemble the offline web payload for the Android WebView shell."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

MOBILE = Path(__file__).resolve().parents[1]
REPO = MOBILE.parent
WEB = MOBILE / "www"

HUB_FILES = [
    "index.html",
    "projects.json",
    "manifest.json",
    "icon.svg",
    "icon-192.png",
    "icon-512.png",
    "icon-maskable-512.png",
    "apple-touch-icon.png",
]

REPOS = {
    "game": "https://github.com/wzysgsg6/gsf-mobile-game.git",
    "class": "https://github.com/wzysgsg6/today-class.git",
}

BACK_SCRIPT = """
<script>
(function () {
  if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.App) {
    window.Capacitor.Plugins.App.addListener('backButton', function (state) {
      if (state.canGoBack) window.history.back();
      else window.Capacitor.Plugins.App.exitApp();
    });
  }
})();
</script>
"""

OLD_CLASS_KEY_BLOCK = """  if (!state.keyB64) {
    $('#todayView').innerHTML = '<div class="notice"><strong>缺少访问密钥</strong><p>请从完整链接打开本页。</p></div>';
    $('#heroStatus').textContent = '缺少访问密钥';
    $('#pdfBtn')?.classList.add('hidden');
    return;
  }
"""

NEW_CLASS_KEY_BLOCK = """  if (!state.keyB64) {
    $('#todayView').innerHTML = `
      <div class="notice">
        <strong>输入课表密钥</strong>
        <p>密钥只保存在本机，不会写入安装包。</p>
        <input id="ttKeyInput" type="text" inputmode="text" autocomplete="off" placeholder="粘贴课表密钥" style="width:100%;margin-top:12px;padding:12px 14px;border-radius:12px;border:1px solid #cbd5e1;background:#fff;color:#0f172a;font-size:16px;box-sizing:border-box">
        <button id="ttKeySave" type="button" style="width:100%;margin-top:10px;padding:12px 16px;border:0;border-radius:12px;background:#1d4ed8;color:#fff;font-size:16px;font-weight:700">保存并打开</button>
      </div>`;
    $('#heroStatus').textContent = '等待输入密钥';
    const input = $('#ttKeyInput');
    const save = $('#ttKeySave');
    const submitKey = () => {
      const value = input.value.trim();
      if (!value) return;
      localStorage.setItem('tt_key', value);
      state.keyB64 = value;
      init();
    };
    save.addEventListener('click', submitKey);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') submitKey();
    });
    return;
  }
"""

NEW_PDF_FUNCTION = """function bytesToBase64(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function openOriginalPdf() {
  if (!state.keyB64) {
    showToast('缺少访问密钥');
    return;
  }

  try {
    const response = await fetch('./schedule.pdf.enc.json');
    if (!response.ok) throw new Error('PDF 数据读取失败');
    const payload = await response.json();
    const bytes = await decryptBytes(payload, state.keyB64);

    const plugins = window.Capacitor && window.Capacitor.Plugins;
    if (plugins && plugins.Filesystem && plugins.Share) {
      try {
        const fileName = '课程表-' + Date.now() + '.pdf';
        const saved = await plugins.Filesystem.writeFile({
          path: fileName,
          data: bytesToBase64(bytes),
          directory: 'CACHE'
        });
        await plugins.Share.share({
          title: '课程表 PDF',
          url: saved.uri,
          dialogTitle: '用 PDF 阅读器打开课程表'
        });
        return;
      } catch (nativeError) {
        console.warn('Native PDF share failed', nativeError);
      }
    }

    const blobUrl = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
    const win = window.open(blobUrl, '_blank');
    if (!win) window.location.href = blobUrl;
    setTimeout(() => URL.revokeObjectURL(blobUrl), 120000);
  } catch (error) {
    showToast(error.message || 'PDF 打开失败');
  }
}

"""

def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)

def copy_tree(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        ".git",
        ".github",
        ".nojekyll",
        "README.md",
        "package.json",
        "scripts",
    )
    shutil.copytree(src, dst, ignore=ignore)

def inject_back_script(index_path: Path) -> None:
    text = index_path.read_text(encoding="utf-8")
    if "Capacitor.Plugins.App" not in text:
        if "</body>" not in text:
            raise RuntimeError(f"Missing </body> in {index_path}")
        text = text.replace("</body>", BACK_SCRIPT + "\n</body>", 1)
        index_path.write_text(text, encoding="utf-8")

def main() -> None:
    if WEB.exists():
        resolved = WEB.resolve()
        if resolved.parent != MOBILE.resolve():
            raise RuntimeError(f"Unsafe web directory: {resolved}")
        shutil.rmtree(WEB)
    WEB.mkdir(parents=True)

    for name in HUB_FILES:
        src = REPO / name
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, WEB / name)

    with tempfile.TemporaryDirectory(prefix="my-hub-src-") as tmp:
        tmp_path = Path(tmp)
        token = os.environ.get("GITHUB_TOKEN")
        for folder, url in REPOS.items():
            override = os.environ.get(f"{folder.upper()}_SOURCE_DIR")
            if override:
                shutil.copytree(Path(override), tmp_path / folder)
                continue
            clone_url = url
            if token:
                clone_url = url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
            run(["git", "clone", "--depth", "1", clone_url, str(tmp_path / folder)])

        copy_tree(tmp_path / "game", WEB / "game")
        copy_tree(tmp_path / "class", WEB / "class")

    for sw in [WEB / "sw.js", WEB / "game" / "sw.js", WEB / "class" / "sw.js"]:
        if sw.exists():
            sw.unlink()

    projects_path = WEB / "projects.json"
    projects = json.loads(projects_path.read_text(encoding="utf-8"))
    for project in projects.get("projects", []):
        if project.get("id") == "gsf-mobile-game":
            project["url"] = "./game/"
        elif project.get("id") == "today-class":
            project["url"] = "./class/"
    projects_path.write_text(json.dumps(projects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hub_html = WEB / "index.html"
    hub_text = hub_html.read_text(encoding="utf-8")
    hub_text = hub_text.replace("https://wzysgsg6.github.io/gsf-mobile-game/", "./game/")
    hub_text = hub_text.replace("https://wzysgsg6.github.io/today-class/", "./class/")
    hub_html.write_text(hub_text, encoding="utf-8")

    class_app = WEB / "class" / "app.js"
    class_text = class_app.read_text(encoding="utf-8")
    if OLD_CLASS_KEY_BLOCK not in class_text:
        raise RuntimeError("Could not find the class key prompt block in today-class/app.js")
    class_text = class_text.replace(OLD_CLASS_KEY_BLOCK, NEW_CLASS_KEY_BLOCK, 1)

    pdf_start = class_text.index("async function openOriginalPdf() {")
    pdf_end = class_text.index("function parseISODateUTC(", pdf_start)
    class_text = class_text[:pdf_start] + NEW_PDF_FUNCTION + "\n" + class_text[pdf_end:]
    class_app.write_text(class_text, encoding="utf-8")

    for index_path in [WEB / "index.html", WEB / "game" / "index.html", WEB / "class" / "index.html"]:
        inject_back_script(index_path)

    print(f"Prepared offline web bundle at {WEB}")

if __name__ == "__main__":
    main()
