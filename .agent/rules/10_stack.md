---
trigger: always_on
---

# 10_stack.md - Your Standard Technology Stack

## Why This Stack?
To avoid confusion and maintain consistency across projects, we use **one standardized, modern full-stack framework** that can handle most web application needs.

---

## The Stack

### Frontend & Backend Framework
**Next.js 15** (React 19)
- **Why**: Industry-standard, excellent documentation, huge community
- **What it does**: Handles both your user interface (React) and backend API routes (Node.js) in one framework
- **Language**: TypeScript (for type safety and better error catching)
- **Key benefit**: You only need to learn ONE framework for full-stack development

### Database
**PostgreSQL 16** with **Prisma ORM**
- **Why PostgreSQL**: Industry-standard SQL database, reliable, powerful
- **Why Prisma**: Makes database work easier, type-safe, great for learning
- **Key benefit**: Prisma generates TypeScript types from your database, catching errors before runtime

### Styling
**Tailwind CSS**
- **Why**: Utility-first CSS, no separate CSS files to manage
- **Philosophy**: Keep it simple and functional over fancy designs
- **Key benefit**: Faster development, consistent styling, easy to learn

### Package Manager
**npm** (comes with Node.js)
- **Why**: Standard, reliable, well-documented
- **Note**: Stick with npm, don't mix with yarn or pnpm

### Version Control
**Git & GitHub**
- **Why**: Industry standard for code versioning
- **Workflow**: Commit early and often with clear messages

### Deployment
**Vercel** (recommended) or **Railway**
- **Why Vercel**: Made by Next.js creators, dead-simple deployment
- **Why Railway**: Good alternative with easy database hosting
- **Key benefit**: Deploy with a single command or git push

### Environment & Runtime
- **Node.js 20 LTS** (Long Term Support)
- **Package Manager**: npm (built into Node.js)

---

## Project Structure Convention

Every Next.js project should follow this standard structure:

```
my-project/
├── app/                    # Next.js 15 App Router (pages and layouts)
│   ├── api/               # Backend API routes
│   ├── (routes)/          # Frontend pages
│   └── layout.tsx         # Root layout
├── components/            # Reusable UI components
│   ├── ui/               # Basic UI elements (buttons, inputs, etc.)
│   └── features/         # Feature-specific components
├── lib/                   # Utility functions and helpers
│   ├── db.ts             # Prisma database client
│   └── utils.ts          # General utilities
├── prisma/               # Database schema and migrations
│   └── schema.prisma     # Database schema definition
├── public/               # Static assets (images, fonts, etc.)
├── .env.local           # Environment variables (NEVER commit this!)
├── .env.example         # Template for environment variables (safe to commit)
├── .gitignore           # Files to exclude from Git
├── package.json         # Project dependencies
├── tsconfig.json        # TypeScript configuration
├── tailwind.config.ts   # Tailwind CSS configuration
└── README.md            # Project documentation
```

---

## When to Deviate from This Stack

**Don't deviate unless**:
- The project has a specific, documented reason (e.g., client requirement)
- You explicitly ask to explore alternatives
- The stack genuinely cannot solve the problem

**If deviation is needed**:
1. Discuss why the standard stack won't work
2. Present alternative options with clear pros/cons
3. Get explicit approval before proceeding
4. Document the deviation and reasoning in the README

---

## Required Tools Installation

Before starting any project, ensure these are installed:

1. **Node.js 20 LTS**: [https://nodejs.org](https://nodejs.org)
2. **Git**: [https://git-scm.com](https://git-scm.com)
3. **PostgreSQL**: [https://www.postgresql.org](https://www.postgresql.org) or use Railway/Vercel Postgres
4. **VS Code** (recommended): [https://code.visualstudio.com](https://code.visualstudio.com)
   - With extensions: ESLint, Prettier, Prisma, Tailwind CSS IntelliSense

---

## Version Reference

Always use the latest stable versions unless there's a specific reason not to:

- **Next.js**: 15.x
- **React**: 19.x
- **TypeScript**: 5.x
- **Prisma**: 6.x
- **PostgreSQL**: 16.x
- **Tailwind CSS**: 4.x
- **Node.js**: 20.x LTS

Check current versions with:
```bash
node --version
npm --version
```

---

## API Integration

For external APIs, use:
- **HTTP Client**: Native `fetch` (built into Next.js)
- **Environment Variables**: Always store API keys in `.env.local`
- **Type Safety**: Define TypeScript interfaces for API responses

---

## Key Principles

1. **One Stack to Rule Them All**: Use this stack for all web projects unless impossible
2. **Type Safety Everywhere**: TypeScript catches errors before they happen
3. **Database-Driven**: Use PostgreSQL + Prisma for any data persistence needs
4. **Git from Day One**: Initialize Git on every project immediately
5. **Environment Variables**: Never hardcode secrets, always use `.env.local`
