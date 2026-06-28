/** Guided filter — згладжує маску по краях оригінального фото (як у старому script.js). */
class GuidedFilter {
  constructor(imageData, r, eps) {
    this.width = imageData.width;
    this.height = imageData.height;
    this.r = r;
    this.eps = eps;

    const data = imageData.data;
    this.I = new Float32Array(this.width * this.height);
    for (let i = 0, j = 0; i < data.length; i += 4, j++) {
      this.I[j] = (0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) / 255.0;
    }

    this.mean_I = this._boxFilter(this.I);
    const mean_II = this._boxFilter(this.I.map((x) => x * x));
    this.var_I = new Float32Array(this.I.length);
    for (let i = 0; i < this.I.length; i++) {
      this.var_I[i] = mean_II[i] - this.mean_I[i] * this.mean_I[i];
    }
  }

  _boxFilter(src) {
    const dst = new Float32Array(src.length);
    const r = this.r;
    const w = this.width;
    const h = this.height;

    for (let y = 0; y < h; y++) {
      let sum = 0;
      for (let i = 0; i <= r; i++) sum += src[y * w + i];
      dst[y * w] = sum;
      for (let x = 1; x < w; x++) {
        if (x + r < w) sum += src[y * w + x + r];
        if (x - r - 1 >= 0) sum -= src[y * w + x - r - 1];
        dst[y * w + x] = sum;
      }
    }

    const tempDst = new Float32Array(dst);
    for (let x = 0; x < w; x++) {
      let sum = 0;
      for (let i = 0; i <= r; i++) sum += tempDst[i * w + x];
      dst[x] = sum;
      for (let y = 1; y < h; y++) {
        if (y + r < h) sum += tempDst[(y + r) * w + x];
        if (y - r - 1 >= 0) sum -= tempDst[(y - r - 1) * w + x];
        dst[y * w + x] = sum;
      }
    }

    const area = (2 * r + 1) * (2 * r + 1);
    for (let i = 0; i < dst.length; i++) dst[i] /= area;
    return dst;
  }

  filter(maskImageData) {
    const p = new Float32Array(this.I.length);
    for (let i = 0; i < maskImageData.data.length; i += 4) {
      p[i / 4] = maskImageData.data[i] / 255.0;
    }

    const mean_p = this._boxFilter(p);
    const mean_Ip = this._boxFilter(this.I.map((I, i) => I * p[i]));
    const cov_Ip = new Float32Array(this.I.length);
    for (let i = 0; i < this.I.length; i++) {
      cov_Ip[i] = mean_Ip[i] - this.mean_I[i] * mean_p[i];
    }

    const a = new Float32Array(this.I.length);
    const b = new Float32Array(this.I.length);
    for (let i = 0; i < this.I.length; i++) {
      a[i] = cov_Ip[i] / (this.var_I[i] + this.eps);
      b[i] = mean_p[i] - a[i] * this.mean_I[i];
    }

    const mean_a = this._boxFilter(a);
    const mean_b = this._boxFilter(b);
    const dst = new Float32Array(this.I.length);
    for (let i = 0; i < this.I.length; i++) {
      dst[i] = mean_a[i] * this.I[i] + mean_b[i];
    }
    return dst;
  }
}
