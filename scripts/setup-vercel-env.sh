#!/bin/bash
# Script to add environment variables to Vercel
# Run this to configure your Vercel deployment

echo "Adding environment variables to Vercel..."

# Database
vercel env add DATABASE_URL production

# API Keys
vercel env add API_PASSWORD production
vercel env add ADMIN_PASSWORD production

# Redis (Upstash)
vercel env add UPSTASH_REDIS_REST_URL production
vercel env add UPSTASH_REDIS_REST_TOKEN production

# Cloudinary
vercel env add CLOUDINARY_CLOUD_NAME production
vercel env add CLOUDINARY_API_KEY production
vercel env add CLOUDINARY_API_SECRET production

# ElevenLabs
vercel env add ELEVENLABS_API_KEY production

# Optional
vercel env add SENTRY_DSN production

echo "✓ Environment variables configured!"
echo ""
echo "Or set them manually in Vercel dashboard:"
echo "https://vercel.com/your-project/settings/environment-variables"
