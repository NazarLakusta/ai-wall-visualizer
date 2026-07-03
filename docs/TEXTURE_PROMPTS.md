# Промпти для генерації текстур декоративки (dirt-map / luminance)

Текстури для міні-додатку мають працювати як **карта яскравості** (аналог dirt map у 3ds Max): переважно біло-сірий діапазон RGB **220–255**, без темно-сірих плям. Колір відтінку задається окремо (hex); текстура лише додає легкий рельєф.

Після генерації:
1. Переконайтесь, що середня яскравість > 90% (підніміть levels у Photoshop / GIMP).
2. Зробіть **seamless tile** (без швів при повторі).
3. Розмір: **1024×1024** або **2048×2048** PNG.
4. Завантажте в адмінці: Матеріали → Текстура.

---

## KROINZ Beige German Silk (бежевий німецький шовк)

```
Seamless tileable decorative wall paint texture, German silk finish, ultra subtle fine brush strokes and soft satin micro-pattern, almost flat, luminance map style, grayscale only, RGB values between 225 and 255, no dark gray patches, no color tint, high key white-light-gray, soft ambient lighting, macro close-up, 2048x2048, photorealistic material reference for 3D tinting
```

**Negative prompt:** `dark gray, black spots, strong contrast, colored pigment, marble veins, heavy plaster chunks, visible seams, text, watermark`

**texture_scale в адмінці:** `1.2`

---

## KROINZ White German Silk (білий німецький шовк)

```
Seamless tileable white silk decorative paint wall texture, delicate pearlescent sheen suggestion only in grayscale brightness variation, very fine horizontal silk streaks, luminance map, RGB 230-255, minimal contrast, soft matte-satin hybrid, no dark areas, neutral white-gray, macro texture for color tinting overlay, 2048x2048
```

**Negative prompt:** `dark gray, muddy, brown cast, blue cast, high contrast, cracks, dirt, stains, seam, logo`

**texture_scale:** `1.2`

---

## KROINZ Sahara Velvet (декоративна штукатурка «Сахара»)

```
Seamless tileable decorative plaster texture Sahara velvet effect, fine sandy grain with gentle organic waves, stucco relief very subtle, luminance map grayscale RGB 220-250, soft desert sand surface, no deep shadows, no dark gray, tileable pattern, macro wall sample, 2048x2048 for tint color overlay
```

**Negative prompt:** `deep cracks, coarse aggregate, dark mortar, strong shadow, high contrast, colored sand, orange tint baked in, seam, text`

**texture_scale:** `1.5`

---

## Постобробка (рекомендовано)

1. **Desaturate** повністю (якщо модель дала відтінок).
2. **Levels / Curves:** чорна точка ≈ 200–210, біла ≈ 255.
3. Перевірка: накладіть тестовий колір `#C8A882` у Photoshop (Multiply → замініть на Soft Light 10–15% або просто заливка з режимом Color) — не повинно з’являтися «брудно-сірого».

## Як працює в рендері

`mini-app/js/renderer.js` множить обраний hex на **яскравість текстури** (0.9–1.0), а не на кожен RGB-канал окремо — тому світла dirt-map не залишає сірих плям після тонування.
