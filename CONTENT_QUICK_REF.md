# GrokProxy Content Generation - Quick Reference

## 🚀 Quick Start

### Generate Single Image

```bash
python content_generator.py image "a beautiful sunset over mountains"
```

### Generate with Style

```bash
python content_generator.py image "futuristic city" --style cinematic
```

### Generate Video

```bash
python content_generator.py video "time-lapse of clouds" --duration 10
```

### Batch Generate from File

```bash
python content_generator.py batch sample_prompts.txt --type image --style photorealistic
```

---

## 📝 Available Styles

- `photorealistic` - Photo-like quality (default)
- `cinematic` - Movie-like with dramatic lighting
- `artistic` - Painterly, artistic style
- `anime` - Anime/manga style
- `cartoon` - Cartoon style

---

## 🎨 Example Prompts

### Images

```
A majestic dragon flying over mountains
A futuristic cyberpunk city at night
An underwater coral reef scene
A cozy cabin in snowy forest
A space station orbiting Earth
```

### Videos

```
Time-lapse of sunset over ocean
Slow zoom into a galaxy
Camera pan across mountain range
Rotating view of Earth from space
Flowers blooming in garden
```

---

## 💡 Tips for Best Results

1. **Be Specific**: "A red sports car on coastal highway at sunset" > "A car"
2. **Add Details**: Include lighting, mood, composition details
3. **Use Keywords**: "8k", "detailed", "professional", "cinematic"
4. **Specify Style**: Add style keywords like "photorealistic" or "artistic"
5. **Set Context**: Describe the scene, not just the subject

---

## 📊 Monitor Usage

### Check generation history

```bash
# View recent generations
psql "$DATABASE_URL" -c "
  SELECT created_at, model, status, latency_ms
  FROM generations
  ORDER BY created_at DESC
  LIMIT 10;
"

# Check costs
psql "$DATABASE_URL" -c "
  SELECT
    DATE(created_at) as date,
    COUNT(*) as requests,
    SUM(total_cost_micro_usd) / 1000000.0 as cost_usd
  FROM token_usage
  GROUP BY DATE(created_at)
  ORDER BY date DESC
  LIMIT 7;
"
```

---

## 🔧 Configuration

### Environment Variables

```bash
export PROXY_URL="http://localhost:8000"
export API_KEY="Bcmoney69$"
```

### Output Directory

Generated content is saved to: `generated_content/`

---

## 🎯 Use Cases

### Social Media Content

```bash
# Instagram posts
python content_generator.py image "product photo for Instagram, clean background, professional lighting" --style photorealistic

# YouTube thumbnails
python content_generator.py image "YouTube thumbnail, bold text, high contrast, eye-catching" --style cinematic
```

### Marketing Materials

```bash
# Product mockups
python content_generator.py image "smartphone on desk with coffee, minimalist setup, professional photography" --style photorealistic

# Hero images
python content_generator.py image "abstract technology background, blue and purple gradient, modern" --style artistic
```

### Video Content

```bash
# Intro sequences
python content_generator.py video "logo reveal with particles, professional, smooth animation" --duration 5

# Background videos
python content_generator.py video "abstract flowing shapes, calming, loop-able" --duration 10
```

---

## 📚 Full Documentation

See **[CONTENT_GENERATION_GUIDE.md](./CONTENT_GENERATION_GUIDE.md)** for:

- Complete Python API examples
- Advanced workflows
- Error handling
- Batch processing
- Cost optimization
- Best practices

---

**Happy Creating!** 🎨✨
