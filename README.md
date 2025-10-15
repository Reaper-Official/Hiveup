# 🎯 Contest Platform - SaaS de Gestion de Concours

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node Version](https://img.shields.io/badge/node-%3E%3D20.0.0-brightgreen)](https://nodejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)](https://www.typescriptlang.org/)
[![NestJS](https://img.shields.io/badge/NestJS-10.0-red)](https://nestjs.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.0-black)](https://nextjs.org/)

Plateforme SaaS complète de création et gestion de concours avec intégrations sociales multiples (Discord, YouTube, Twitch, Instagram, Twitter/X, etc.). Solution clé en main pour organiser des giveaways, contests et sweepstakes avec système de points, tirage au sort sécurisé et analytics avancés.

## ✨ Fonctionnalités Principales

- 🎮 **Multi-plateformes** : Intégration native avec 10+ réseaux sociaux
- 🏆 **Templates de concours** : Giveaways, Contests, Sweepstakes prêts à l'emploi
- 📊 **Analytics temps réel** : Dashboard complet avec métriques de conversion
- 🔒 **Anti-fraude** : Détection automatique, fingerprinting, validation manuelle
- 💳 **Monétisation** : Plans freemium avec Stripe, facturation à l'usage
- 🌍 **Multi-tenant** : Organisations avec RBAC complet
- 📱 **Widget embarquable** : JavaScript snippet responsive et personnalisable
- 🎲 **Tirage sécurisé** : CSPRNG avec audit trail et certificat
- 📧 **Notifications** : Email, webhooks, Zapier ready
- 🌐 **i18n** : Français et Anglais natifs

## 🚀 Démarrage Rapide

### Prérequis

- **Node.js** 20.0+ et **pnpm** 8.0+
- **Docker** 24.0+ et **Docker Compose** 2.20+
- **PostgreSQL** 15+ (ou via Docker)
- **Redis** 7+ (ou via Docker)
- Compte **Stripe** (pour les paiements)
- Comptes développeurs pour les réseaux sociaux (optionnel)

### Installation en 5 minutes

```bash
# 1. Cloner le repository
git clone https://github.com/your-org/contest-platform.git
cd contest-platform

# 2. Installer les dépendances
pnpm install

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos clés API

# 4. Démarrer l'infrastructure
docker-compose up -d

# 5. Initialiser la base de données
pnpm db:setup

# 6. Lancer le développement
pnpm dev

# 🎉 C'est parti!
# Frontend: http://localhost:3000
# API: http://localhost:4000
# API Docs: http://localhost:4000/api/docs
```

## 📁 Structure du Projet

```
contest-platform/
├── apps/
│   ├── web/          # Frontend Next.js
│   ├── api/          # Backend NestJS
│   └── widget/       # Widget embarquable
├── packages/
│   ├── shared/       # Types et utils partagés
│   ├── sdk/          # SDK TypeScript
│   └── ui/           # Composants UI partagés
├── infrastructure/   # Docker, K8s, Terraform
├── database/         # Migrations et seeds
└── docs/            # Documentation complète
```

## 🔧 Configuration

### Variables d'Environnement Essentielles

```env
# Base
NODE_ENV=development
PORT=4000
FRONTEND_URL=http://localhost:3000

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/contest_platform
REDIS_URL=redis://localhost:6379

# Security (générer avec: openssl rand -hex 32)
JWT_SECRET=your-jwt-secret-min-32-chars
ENCRYPTION_KEY=your-encryption-key-min-32-chars
COOKIE_SECRET=your-cookie-secret

# Stripe
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OAuth Providers (optionnel)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...

# Email (SendGrid/SES/SMTP)
EMAIL_PROVIDER=smtp
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASS=

# Storage (MinIO en dev, S3 en prod)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=contest-platform

# Social APIs (voir docs/connectors/)
YOUTUBE_API_KEY=...
TWITCH_CLIENT_ID=...
INSTAGRAM_APP_ID=...
# ... autres selon besoins
```

## 🎮 Utilisation

### Créer votre premier concours

1. **Inscription** : Créez un compte sur http://localhost:3000/signup
2. **Organisation** : Créez votre organisation
3. **Nouveau concours** : Cliquez sur "Créer un concours"
4. **Template** : Choisissez un template ou partez de zéro
5. **Actions** :
