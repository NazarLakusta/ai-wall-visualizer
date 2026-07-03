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

---

# Imagine Decor (вітрина / зразки)

Усі промпти — **grayscale luminance map**, RGB 220–255. Колір (беж, сірий, блакитний, золото) задаєш відтінком у каталозі; у текстурі лише рельєф і блиск.

---

## Silk (шовк)

```
Seamless tileable decorative silk wall paint texture, smooth satin pearlescent finish, very subtle broad trowel sweeps, soft horizontal silk streaks, luminance map grayscale RGB 230-255, minimal contrast, elegant matte-satin hybrid, no dark patches, macro wall sample, 2048x2048 for color tint overlay
```

**Negative:** `dark gray, strong contrast, coarse grain, cracks, colored tint, visible seam, text, watermark`

**texture_scale:** `1.0–1.2`

---

## Las Vegas (перламутр / сріблястий шовк)

```
Seamless tileable pearlescent decorative paint texture Las Vegas effect, fine uniform sandy micro-grain, soft metallic sheen expressed only as grayscale brightness variation, silvery white-light-gray, luminance map RGB 225-255, subtle sparkle highlights, smooth satin plaster, no dark areas, tileable, 2048x2048
```

**Negative:** `dark gray, black spots, heavy glitter, strong color cast, blue tint, coarse aggregate, seam, logo`

**texture_scale:** `1.2`

---

## Stresa (дрібнозернистий «пісок»)

```
Seamless tileable fine sandy decorative plaster texture Stresa effect, uniform dense micro-grain like fine sandpaper, subtle all-over sparkle as tiny bright dots in grayscale only, cool light gray luminance map RGB 225-252, matte with micro shimmer, no deep shadows, tileable macro, 2048x2048
```

**Negative:** `large grains, dark gray, strong contrast, colored sand, cracks, orange cast, seam, text`

**texture_scale:** `1.3`

---

## Sahara (дюни / вітровий пісок)

```
Seamless tileable decorative plaster Sahara sand dune texture, pearlescent base with fine sand particles, sweeping wind-swept directional swirls and organic wave patterns, luminance map grayscale RGB 220-250, warm neutral gray only no color, soft relief, no dark shadows, tileable wall macro, 2048x2048
```

**Negative:** `deep cracks, dark gray patches, strong orange color baked in, coarse rocks, high contrast shadows, seam, watermark`

**texture_scale:** `1.4–1.6`

---

## Crystal Shine (кристалічний блиск)

```
Seamless tileable decorative plaster Crystal Shine texture, pearlescent frost-like surface, irregular patches of higher sheen as brighter grayscale areas only, fine crystalline sparkle, very pale champagne-gray luminance map RGB 228-255, delicate granular relief, no dark gray, tileable, 2048x2048 for tinting
```

**Negative:** `dark gray, black crystals, rainbow color, heavy glitter chunks, strong contrast, colored frost, seam, text`

**texture_scale:** `1.3`

---

## Glitter / кристалічний шовк (без назви на зразку)

```
Seamless tileable decorative wall texture fine glitter crystal effect, many tiny reflective particles as small bright grayscale dots on light gray base, uniform fine granular sparkle, luminance map RGB 225-255, cool light gray, no large dark voids, subtle depth, tileable macro, 2048x2048
```

**Negative:** `large glitter flakes, dark background, strong contrast, colored glitter, pink blue gold tint in texture, seam, logo`

**texture_scale:** `1.2`

---

## Marcopolo Luxury (металік / шампань)

```
Seamless tileable luxury decorative plaster Marcopolo metallic texture, fine irregular ridges and brushed patterns, champagne gold sheen expressed only as grayscale brightness waves RGB 220-248, rich micro-relief, soft metallic highlights without color, no dark gray patches, tileable macro wall, 2048x2048
```

**Negative:** `solid gold color, dark bronze, black grooves, high contrast shadows, rust, colored metal, seam, text`

**texture_scale:** `1.4`

**Примітка:** для золотого відтінку візуалізаторі обери hex типу `#D4C4A0`; текстура дає лише рельєф металу.

---

## Mikrocement (мікроцемент)

```
Seamless tileable microcement wall texture, ultra smooth polished concrete finish, very fine subtle trowel marks, almost flat, luminance map grayscale RGB 232-255, minimal micro-pores, soft matte cement, no cracks no dark spots, modern seamless tile, 2048x2048
```

**Negative:** `heavy cracks, aggregate stones, dark gray patches, strong stains, orange rust, high contrast, seam, text`

**texture_scale:** `0.8–1.0`

---

## Velvet — хмарний / замша (сірий моттл)

```
Seamless tileable decorative velvet plaster texture, soft mottled cloudy suede effect, organic tone variation in grayscale only RGB 222-248, gentle depth clouds, matte velvety plaster, no dark gray blobs, smooth transitions, tileable macro, 2048x2048
```

**Negative:** `sharp dark patches, black spots, colored clouds, high contrast, coarse grain, seam, watermark`

**texture_scale:** `1.3`

---

## Velvet — травертин / пористий

```
Seamless tileable travertine-like decorative plaster texture, porous pitted surface with small holes and pits as slightly darker gray dots RGB 215-245 max, rough stucco relief, light stone plaster, luminance map no color, subtle pitting, tileable, 2048x2048
```

**Negative:** `deep black holes, strong shadows, dark gray below 200, colored stone, large cracks, seam, text`

**texture_scale:** `1.5`

**Примітка:** після генерації підніми чорну точку в levels, щоб найтемніші пори були не нижче ~210.

---

## Velvet — золоті вкраплення (акцент)

```
Seamless tileable decorative plaster texture velvet base with scattered metallic flake accents, fine gold bronze flakes as brighter grayscale specks only on light gray suede base, luminance map RGB 220-255, soft mottled background, irregular small bright spots, no dark gray base, tileable, 2048x2048
```

**Negative:** `solid gold surface, dark blue gray base color baked in, large gold sheets, black spots, strong contrast, colored flakes, seam`

**texture_scale:** `1.4`

**Примітка:** базовий колір (сіро-блакитний) — hex відтінку; «золото» у текстурі лише як світліші плями ~240–255.

---

## Velvet — геометричний патерн (акцент)

```
Seamless tileable decorative wall texture, light gray cloudy velvet plaster background with subtle embossed geometric line pattern, intersecting thin lines as slightly brighter grayscale relief only, luminance map RGB 225-255, low contrast pattern, soft suede base, tileable repeat, 2048x2048
```

**Negative:** `dark lines, black grid, strong contrast, colored pattern, wallpaper print, thick black strokes, seam, text`

**texture_scale:** `1.2`

---

## Velvet — вертикальні мазки

```
Seamless tileable decorative plaster texture with subtle vertical trowel brush marks, sage-neutral gray luminance map RGB 228-255, soft directional streaks catching light, matte plaster, minimal contrast, no dark grooves, seamless tile, 2048x2048
```

**Negative:** `horizontal marks, dark gray strokes, deep grooves, colored green tint, high contrast, cracks, seam`

**texture_scale:** `1.1`

---

## Marmorin — шорсткі «корки» / aged plaster

```
Seamless tileable Marmorin decorative plaster texture, smooth base with irregular raised rough patches and coarse granular islands, same-tone relief in grayscale luminance map RGB 218-248, weathered plaster map-like spots, tactile depth without dark gray, tileable macro, 2048x2048
```

**Negative:** `black cracks, dark gray below 200, strong color beige baked in, huge chunks, high shadow contrast, seam, text`

**texture_scale:** `1.6`

---

## Marmorin — рівномірний дрібний пісок

```
Seamless tileable Marmorin fine sandy plaster texture, uniform fine grain matte finish, consistent micro-sand across surface, luminance map grayscale RGB 230-255, very subtle variation, modern smooth marmorin, no patches no dark spots, tileable, 2048x2048
```

**Negative:** `rough patches, dark gray, coarse aggregate, colored tint, cracks, seam, watermark`

**texture_scale:** `1.2`

---

## Marmorin — тиснений орнамент + корки

```
Seamless tileable decorative Marmorin plaster texture, embossed floral damask-like pattern as subtle raised relief in grayscale, combined with small rough weathered patches, luminance map RGB 220-250, antique decorative wall, low contrast ornament, no dark gray, tileable, 2048x2048
```

**Negative:** `dark ornament lines, black pattern, high contrast emboss, colored pattern, deep shadows, seam, text, logo`

**texture_scale:** `1.5`

---

## Гладка матова (темний відтінок — teal / синьо-зелений)

Для суцільних глибоких кольорів без рельєфу — майже плоска текстура:

```
Seamless tileable ultra smooth matte decorative paint wall texture, almost flat micro-variation only, luminance map grayscale RGB 235-255, minimal texture, soft powder matte, no visible pattern, tileable, 2048x2048 for deep color tint overlay
```

**Negative:** `grain, plaster relief, dark spots, gloss, pattern, seam, text`

**texture_scale:** `0.7–0.9`

**Примітка:** колір `#2A5F5F` або інший темний — тільки через hex відтінку в каталозі.

---

## Швидка шпаргалка по лінійках

| Зразок на вітрині | Лінійка | Ключові слова для промпту |
|---|---|---|
| Silk | Silk | satin, broad sweeps, pearlescent |
| Las Vegas | Las Vegas | pearlescent, fine sand, silvery |
| Stresa | Stresa | fine grain, micro sparkle |
| Sahara | Sahara | sand dunes, wind swirls |
| Crystal Shine | Crystal Shine | frost sparkle, bright patches |
| Marcopolo luxury | Marcopolo | metallic ridges, champagne sheen |
| Mikrocement | Mikrocement | smooth concrete, polished |
| Хмарний сірий | Velvet | mottled suede clouds |
| Травертин | Velvet | porous pits, travertine |
| Золоті плями | Velvet accent | flakes as bright specks |
| Геометрія | Velvet accent | embossed line grid |
| Вертикальні мазки | Velvet | vertical trowel marks |
| Корки / map | Marmorin | rough raised patches |
| Рівний пісок | Marmorin | uniform fine grain |
| Орнамент | Marmorin | damask emboss + patches |
| Темний гладкий | — | almost flat matte |

