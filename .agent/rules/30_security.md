---
trigger: always_on
---

# 30_security.md - Security Standards & Best Practices

## Core Security Principle
**Always prioritize security, even if it adds complexity.** Better to be safe than to have data breaches or security vulnerabilities.

---

## Environment Variables & Secrets

### The Golden Rule
**NEVER hardcode sensitive information in code.** Always use environment variables.

### What Counts as Sensitive
- API keys
- Database passwords
- Authentication secrets
- Third-party service credentials
- OAuth client IDs and secrets
- Encryption keys
- Webhook secrets

### How to Handle Secrets

#### 1. Use `.env.local` for local development
```bash
# .env.local (NEVER commit this file!)

# Database
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"

# External APIs
OPENAI_API_KEY="sk-..."
STRIPE_SECRET_KEY="sk_test_..."

# Authentication
NEXTAUTH_SECRET="your-secret-here"
NEXTAUTH_URL="http://localhost:3000"
```

#### 2. Create `.env.example` template
```bash
# .env.example (SAFE to commit - no real values!)

# Database
DATABASE_URL="postgresql://user:password@localhost:5432/dbname"

# External APIs
OPENAI_API_KEY="your-openai-key-here"
STRIPE_SECRET_KEY="your-stripe-secret-here"

# Authentication
NEXTAUTH_SECRET="generate-random-secret"
NEXTAUTH_URL="http://localhost:3000"
```

#### 3. Add to `.gitignore`
```
# .gitignore
.env.local
.env*.local
```

#### 4. Use in Code
```typescript
// ✅ Correct
const apiKey = process.env.OPENAI_API_KEY;

// ❌ NEVER do this
const apiKey = "sk-1234567890abcdef";
```

### Server-Side vs Client-Side Variables

**Important**: In Next.js, only variables prefixed with `NEXT_PUBLIC_` are exposed to the browser.

```bash
# .env.local

# ❌ Secret - server-only (no NEXT_PUBLIC_ prefix)
DATABASE_URL="..."
STRIPE_SECRET_KEY="..."

# ✅ Public - safe for browser (has NEXT_PUBLIC_ prefix)
NEXT_PUBLIC_API_URL="https://api.example.com"
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

**Rule**: If it's a secret, it should NEVER have `NEXT_PUBLIC_` prefix.

---

## Authentication & Authorization

### User Authentication
Use a proven solution, never roll your own:
- **Recommended**: NextAuth.js (Auth.js)
- **Why**: Battle-tested, handles edge cases, regular security updates

### Password Handling
```typescript
// ✅ Use a proper hashing library
import bcrypt from 'bcryptjs';

async function hashPassword(password: string): Promise<string> {
  const salt = await bcrypt.genSalt(10);
  return bcrypt.hash(password, salt);
}

async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

// ❌ NEVER store passwords in plain text
// ❌ NEVER use simple hashing like MD5 or SHA1
```

### Session Management
```typescript
// Use secure session configuration
export const authOptions = {
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  cookies: {
    sessionToken: {
      name: '__Secure-next-auth.session-token',
      options: {
        httpOnly: true,  // ✅ Prevents JavaScript access
        secure: true,    // ✅ HTTPS only
        sameSite: 'lax', // ✅ CSRF protection
      },
    },
  },
};
```

### Protecting API Routes
```typescript
// app/api/protected/route.ts

import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';

export async function GET() {
  // Check if user is authenticated
  const session = await getServerSession(authOptions);

  if (!session) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // Check if user has required permissions
  if (session.user.role !== 'admin') {
    return NextResponse.json(
      { error: 'Forbidden' },
      { status: 403 }
    );
  }

  // User is authorized, proceed
  return NextResponse.json({ data: 'sensitive data' });
}
```

---

## Input Validation & Sanitization

### Always Validate User Input
```typescript
// ✅ Use a validation library
import { z } from 'zod';

// Define schema
const userSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
  age: z.number().min(0).max(150),
});

// Validate input
export async function POST(request: Request) {
  try {
    const body = await request.json();

    // This will throw if validation fails
    const validatedData = userSchema.parse(body);

    // Use validatedData (it's now type-safe and validated)
    const user = await prisma.user.create({
      data: validatedData,
    });

    return NextResponse.json({ user });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    return NextResponse.json(
      { error: 'Server error' },
      { status: 500 }
    );
  }
}
```

### SQL Injection Prevention
```typescript
// ✅ Use Prisma (safe - parameterized queries)
const user = await prisma.user.findUnique({
  where: { email: userInput }
});

// ❌ NEVER use raw SQL with user input
const result = await prisma.$queryRaw`
  SELECT * FROM users WHERE email = ${userInput}
`;
// This is vulnerable to SQL injection!

// ✅ If you must use raw SQL, use proper parameterization
const result = await prisma.$queryRaw`
  SELECT * FROM users WHERE email = ${Prisma.sql([userInput])}
`;
```

### XSS (Cross-Site Scripting) Prevention
```typescript
// ✅ React automatically escapes output
function UserProfile({ name }: { name: string }) {
  return <div>{name}</div>; // Safe, React escapes this
}

// ⚠️ Using dangerouslySetInnerHTML requires sanitization
import DOMPurify from 'isomorphic-dompurify';

function RichTextContent({ html }: { html: string }) {
  const cleanHTML = DOMPurify.sanitize(html);
  return <div dangerouslySetInnerHTML={{ __html: cleanHTML }} />;
}

// ❌ NEVER do this without sanitization
function UnsafeComponent({ html }: { html: string }) {
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

---

## CORS (Cross-Origin Resource Sharing)

### API Route CORS Configuration
```typescript
// app/api/public/route.ts

import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const data = { message: 'Hello World' };

  return NextResponse.json(data, {
    headers: {
      // Only allow specific origins
      'Access-Control-Allow-Origin': process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}

// ❌ NEVER use '*' for Access-Control-Allow-Origin in production
// 'Access-Control-Allow-Origin': '*'  // Too permissive!
```

---

## Rate Limiting

### Protecting API Endpoints
```typescript
// lib/rate-limit.ts
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

// Create rate limiter (10 requests per 10 seconds)
const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '10 s'),
});

export async function checkRateLimit(identifier: string) {
  const { success, limit, reset, remaining } = await ratelimit.limit(identifier);

  return {
    allowed: success,
    limit,
    remaining,
    reset,
  };
}

// app/api/sensitive/route.ts
import { checkRateLimit } from '@/lib/rate-limit';

export async function POST(request: Request) {
  const ip = request.headers.get('x-forwarded-for') || 'unknown';

  const rateLimit = await checkRateLimit(ip);

  if (!rateLimit.allowed) {
    return NextResponse.json(
      { error: 'Too many requests' },
      {
        status: 429,
        headers: {
          'X-RateLimit-Limit': rateLimit.limit.toString(),
          'X-RateLimit-Remaining': rateLimit.remaining.toString(),
          'X-RateLimit-Reset': new Date(rateLimit.reset).toISOString(),
        },
      }
    );
  }

  // Process request
}
```

---

## Dangerous Operations - Warning Protocol

### When to Warn
Always warn and require explicit confirmation before:
- Deleting databases or tables
- Dropping database schemas
- Deleting production data
- Force-pushing to Git
- Deleting files or directories
- Running migrations in production
- Exposing sensitive endpoints publicly

### How to Warn
```typescript
// ⚠️ EXAMPLE WARNING FORMAT

// DANGER: This operation will DELETE ALL USERS from the database
// This action CANNOT be undone
//
// Are you absolutely sure you want to proceed?
// Type "DELETE ALL USERS" to confirm:

async function deleteAllUsers() {
  // Implementation
}
```

### Backup Before Destructive Operations
```bash
# Before running destructive migrations
# 1. Backup database
pg_dump -U user -d database > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migration
npm run migrate

# 3. Verify everything works
# 4. Keep backup for 30 days
```

---

## HTTPS & Secure Connections

### Local Development
- HTTP is acceptable for `localhost`
- Use `http://localhost:3000`

### Production
- **Always use HTTPS** (SSL/TLS)
- Vercel/Railway handle this automatically
- Never serve sensitive data over HTTP

### Redirect HTTP to HTTPS
```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // In production, redirect HTTP to HTTPS
  if (
    process.env.NODE_ENV === 'production' &&
    request.headers.get('x-forwarded-proto') !== 'https'
  ) {
    return NextResponse.redirect(
      `https://${request.headers.get('host')}${request.nextUrl.pathname}`,
      301
    );
  }

  return NextResponse.next();
}
```

---

## File Uploads

### Validation
```typescript
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get('file') as File;

  // Validate file exists
  if (!file) {
    return NextResponse.json(
      { error: 'No file provided' },
      { status: 400 }
    );
  }

  // Validate file size
  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json(
      { error: 'File too large. Maximum size is 5MB' },
      { status: 400 }
    );
  }

  // Validate file type
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    return NextResponse.json(
      { error: 'Invalid file type. Only JPEG, PNG, and WebP are allowed' },
      { status: 400 }
    );
  }

  // Process file...
}
```

---

## Security Checklist

Before deploying any application:

### Environment & Configuration
- [ ] All secrets in environment variables
- [ ] `.env.local` in `.gitignore`
- [ ] `.env.example` committed (no real secrets)
- [ ] `NODE_ENV=production` set for production

### Authentication & Authorization
- [ ] Using proven auth solution (NextAuth.js)
- [ ] Passwords properly hashed (bcrypt)
- [ ] Sessions configured securely (httpOnly, secure, sameSite)
- [ ] All protected routes check authentication
- [ ] Role-based access control implemented where needed

### Data Protection
- [ ] All user input validated (Zod or similar)
- [ ] Prisma used for database queries (no raw SQL with user input)
- [ ] XSS protection (React auto-escaping, DOMPurify for HTML)
- [ ] CORS configured properly (specific origins, not '*')

### API Security
- [ ] Rate limiting implemented for sensitive endpoints
- [ ] API routes return appropriate status codes (401, 403, 429)
- [ ] Error messages don't leak sensitive information
- [ ] File uploads validated (size, type, content)

### Production Deployment
- [ ] HTTPS enabled (automatic with Vercel/Railway)
- [ ] Database backups configured
- [ ] Monitoring/logging set up
- [ ] Security headers configured

---

## When You're Unsure

If you're uncertain about a security decision:
1. **Stop and ask** - don't guess about security
2. **Research** - check official documentation
3. **Default to strict** - better safe than sorry
4. **Document the decision** - explain why you chose this approach

**Remember**: Security mistakes can have serious consequences. It's always better to ask and be cautious.
