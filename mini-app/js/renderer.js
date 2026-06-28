class WallRenderer {
  constructor() {
    this.canvas = document.getElementById("room-canvas");
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });
    this.original = new Image();
    this.mask = new Image();
    this.specular = new Image();
    this.texture = null;
    this.textureData = null;
    this.project = null;
    this.baseData = null;
    this.maskData = null;
    this.specData = null;
    this.gfInstance = null;
    this._blobUrls = [];
    this.authToken = null;
  }

  setAuthToken(token) {
    this.authToken = token;
  }

  _absoluteUrl(path) {
    if (!path) return null;
    if (/^https?:\/\//i.test(path)) return path;
    return `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`;
  }

  async _canvasBlob(format = "image/jpeg", quality = 0.92) {
    return new Promise((resolve, reject) => {
      this.canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("Не вдалось створити зображення"))),
        format,
        quality
      );
    });
  }

  async _uploadResult(blob, filename) {
    if (!this.project?.id || !this.authToken) {
      throw new Error("Немає авторизації для збереження");
    }
    const form = new FormData();
    form.append("file", blob, filename);
    const res = await fetch(`/api/projects/${this.project.id}/result`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.authToken}`,
        "ngrok-skip-browser-warning": "1",
      },
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async _shareFile(file) {
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: "Wall Visualizer" });
      return true;
    }
    return false;
  }

  _desktopDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  _revokeBlobUrls() {
    for (const url of this._blobUrls) {
      URL.revokeObjectURL(url);
    }
    this._blobUrls = [];
  }

  async _loadImage(img, url) {
    if (!url) return;
    const blob = await fetchAssetBlob(url);
    if (!blob.size) {
      throw new Error("порожній файл");
    }
    const objectUrl = URL.createObjectURL(blob);
    this._blobUrls.push(objectUrl);
    return new Promise((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("не вдалось декодувати"));
      img.src = objectUrl;
    });
  }

  _imageToData(img, w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, w, h);
    return ctx.getImageData(0, 0, w, h);
  }

  async init(project) {
    this.project = project;
    this._revokeBlobUrls();

    if (!project.original_url) {
      throw new Error(
        "У проєкті немає фото. Перевірте файли в storage/test і натисніть Тестове фото знову"
      );
    }

    try {
      await this._loadImage(this.original, project.original_url);
      await Promise.all([
        this._loadImage(this.mask, project.mask_url),
        this._loadImage(this.specular, project.specular_url),
      ]);
    } catch (err) {
      this._revokeBlobUrls();
      throw new Error(
        err.message === "ngrok HTML"
          ? "Не вдалось завантажити фото. Перевідкрийте редактор з бота"
          : `Не вдалось завантажити зображення: ${err.message}`
      );
    }

    const w = this.original.naturalWidth;
    const h = this.original.naturalHeight;
    if (!w || !h) {
      this._revokeBlobUrls();
      throw new Error("Зображення кімнати не завантажилось (перевірте original.png)");
    }
    this.canvas.width = w;
    this.canvas.height = h;

    this.baseData = this._imageToData(this.original, w, h);
    this.maskData = this._imageToData(this.mask, w, h);
    this.specData = this._imageToData(this.specular, w, h);

    try {
      this.gfInstance = new GuidedFilter(this.baseData, 6, 0.02 * 255 * 255);
    } catch {
      this.gfInstance = null;
    }
    this.render();
    this._revokeBlobUrls();
  }

  async loadTexture(url) {
    if (!url) {
      this.texture = null;
      this.textureData = null;
      return;
    }
    this.texture = new Image();
    await this._loadImage(this.texture, url);
    const c = document.createElement("canvas");
    c.width = this.texture.naturalWidth;
    c.height = this.texture.naturalHeight;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(this.texture, 0, 0);
    this.textureData = ctx.getImageData(0, 0, c.width, c.height);
  }

  _getColor() {
    if (state.mode === "paint" && state.selectedColor) return state.selectedColor.hex;
    if (state.mode === "decor" && state.selectedMaterialColor) return state.selectedMaterialColor.hex;
    return null;
  }

  _hexToRgb(hex) {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return m
      ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) }
      : { r: 255, g: 255, b: 255 };
  }

  _finishType() {
    const map = { matte: "matte", silk_matte: "satin", gloss: "glossy" };
    return map[state.finish] || "matte";
  }

  _applyFilter(hexColor, texData = null, textureScale = 1.0) {
    if (!this.baseData || !this.maskData || !this.specData) return;

    const finishType = this._finishType();
    const rgb = this._hexToRgb(hexColor);
    const refinedMask = this.gfInstance
      ? this.gfInstance.filter(this.maskData)
      : (() => {
          const p = new Float32Array(this.baseData.data.length / 4);
          for (let i = 0; i < this.maskData.data.length; i += 4) {
            p[i / 4] = this.maskData.data[i] / 255;
          }
          return p;
        })();

    const finalData = new ImageData(
      new Uint8ClampedArray(this.baseData.data),
      this.canvas.width,
      this.canvas.height
    );
    const d = finalData.data;
    const s = this.specData.data;
    const w = this.canvas.width;

    for (let i = 0; i < d.length; i += 4) {
      const maskAlpha = refinedMask[i / 4];
      if (maskAlpha <= 0.05) continue;

      const origR = d[i];
      const origG = d[i + 1];
      const origB = d[i + 2];
      const luminance = (0.299 * origR + 0.587 * origG + 0.114 * origB) / 255.0;
      const specPower = s[i] / 255.0;

      let targetR = rgb.r;
      let targetG = rgb.g;
      let targetB = rgb.b;

      if (texData) {
        const x = (i / 4) % w;
        const y = Math.floor(i / 4 / w);
        const scaledX = x / textureScale;
        const scaledY = y / textureScale;
        const texX = Math.floor(scaledX % texData.width);
        const texY = Math.floor(scaledY % texData.height);
        const ti = (texY * texData.width + texX) * 4;
        targetR = (texData.data[ti] * targetR) / 255;
        targetG = (texData.data[ti + 1] * targetG) / 255;
        targetB = (texData.data[ti + 2] * targetB) / 255;
      }

      let newR;
      let newG;
      let newB;

      if (!texData && hexColor) {
        if (finishType === "matte") {
          const luma = Math.pow(luminance, 0.85);
          newR = luma * targetR;
          newG = luma * targetG;
          newB = luma * targetB;
        } else if (finishType === "satin") {
          const luma = Math.pow(luminance, 0.95);
          const highlight = specPower * 50;
          newR = luma * targetR + highlight;
          newG = luma * targetG + highlight;
          newB = luma * targetB + highlight;
        } else {
          const luma = Math.pow(luminance, 1.2);
          const highlight = Math.pow(specPower, 1.5) * 140;
          newR = luma * targetR + highlight;
          newG = luma * targetG + highlight;
          newB = luma * targetB + highlight;
        }
      } else {
        const adj = Math.min(1.0, luminance * 1.2);
        newR = adj * targetR;
        newG = adj * targetG;
        newB = adj * targetB;
      }

      d[i] = origR * (1 - maskAlpha) + Math.min(255, newR) * maskAlpha;
      d[i + 1] = origG * (1 - maskAlpha) + Math.min(255, newG) * maskAlpha;
      d[i + 2] = origB * (1 - maskAlpha) + Math.min(255, newB) * maskAlpha;
    }

    this.ctx.putImageData(finalData, 0, 0);
  }

  render() {
    if (!this.baseData) return;

    const color = this._getColor();
    if (!color) {
      this.ctx.putImageData(this.baseData, 0, 0);
      return;
    }

    if (state.mode === "decor" && this.textureData) {
      const scale = state.textureScale || 1.0;
      this._applyFilter(color, this.textureData, scale);
    } else {
      this._applyFilter(color, null, 1.0);
    }
  }

  async persistResult() {
    if (!this.project?.id || !this.authToken) return null;
    if (!this._getColor()) return null;
    this.render();
    const filename = `wall-visualizer-${this.project.id}.jpg`;
    const blob = await this._canvasBlob("image/jpeg", 0.92);
    return this._uploadResult(blob, filename);
  }

  async download() {
    const tg = window.Telegram?.WebApp;
    const format = "image/jpeg";
    const ext = "jpg";
    const filename = `wall-visualizer-${this.project?.id || "result"}.${ext}`;
    const blob = await this._canvasBlob(format, 0.92);
    const file = new File([blob], filename, { type: format });

    if (tg?.downloadFile && this.project?.id && this.authToken) {
      try {
        const data = await this._uploadResult(blob, filename);
        const url = this._absoluteUrl(data.download_url);
        const accepted = await new Promise((resolve) => {
          tg.downloadFile({ url, file_name: data.filename || filename }, (ok) => {
            if (ok) {
              tg.showAlert?.("Збережено. Перевірте «Завантаження» (Android) або «Файли» (iPhone).");
            }
            resolve(!!ok);
          });
        });
        if (accepted) return;
      } catch (err) {
        console.warn("telegram download failed", err);
      }
    }

    try {
      const shared = await this._shareFile(file);
      if (shared) return;
    } catch (err) {
      if (err?.name === "AbortError") return;
      console.warn("share failed", err);
    }

    try {
      const data = await this._uploadResult(blob, filename);
      const url = this._absoluteUrl(data.download_url);
      if (tg?.openLink) {
        tg.openLink(url);
        tg.showAlert?.("Відкрийте зображення і збережіть через меню браузера.");
        return;
      }
    } catch (err) {
      console.warn("upload fallback failed", err);
    }

    this._desktopDownload(blob, filename);
    tg?.showAlert?.("На комп'ютері файл з'явиться у папці «Завантаження».");
  }
}

window.renderer = new WallRenderer();
