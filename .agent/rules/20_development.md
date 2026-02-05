---
trigger: always_on
---

# 20_development.md - Development Practices & Code Standards

## Code Quality Standards

### TypeScript Usage
- **Strict Mode**: Always use `"strict": true` in `tsconfig.json`
- **No `any` Type**: Never use `any`. Use `unknown` if type is truly unknown, or define proper interfaces
- **Explicit Types**: Define interfaces for all data structures
- **Example**:
  ```typescript
  // ❌ Bad
  function getUser(id: any): any {
    // ...
  }

  // ✅ Good
  interface User {
    id: string;
    name: string;
    email: string;
  }

  function getUser(id: string): Promise<User> {
    // ...
  }
  ```

### Code Comments
Comments should explain the "why", not the "what":

```typescript
// ❌ Bad comment (obvious what the code does)
// Loop through users
users.forEach(user => {
  // Send email
  sendEmail(user.email);
});

// ✅ Good comment (explains why we're doing this)
// Send welcome emails to users who registered in the last 24 hours
// We batch these to avoid overwhelming the email service
recentUsers.forEach(user => {
  sendWelcomeEmail(user.email);
});
```

**When to add comments**:
- Complex business logic
- Non-obvious workarounds or fixes
- Important TODOs
- Security considerations
- Performance optimizations
- Integration quirks with external APIs

### Error Handling

Always handle errors gracefully:

```typescript
// ✅ Frontend: Show user-friendly errors
try {
  const data = await fetchUserData(userId);
  return data;
} catch (error) {
  console.error('Failed to fetch user data:', error);
  // Show user-friendly message
  toast.error('Unable to load user data. Please try again.');
  return null;
}

// ✅ Backend: Log detailed errors, return safe messages
try {
  const result = await database.query(sql);
  return result;
} catch (error) {
  // Log full error details for debugging
  console.error('Database query failed:', error);
  // Return safe error to client
  return { error: 'An error occurred. Please try again later.' };
}
```

**Error handling rules**:
1. Always catch errors in async operations
2. Log errors with context for debugging
3. Show user-friendly messages to users (never raw error messages)
4. For critical operations, add backup/retry logic
5. Explain error handling strategy when implementing

---

## File Organization

### Component Structure
Follow this pattern for all React components:

```typescript
// components/features/UserProfile.tsx

import { useState, useEffect } from 'react';
import type { User } from '@/types';

// Type definitions at the top
interface UserProfileProps {
  userId: string;
  onUpdate?: (user: User) => void;
}

// Main component
export default function UserProfile({ userId, onUpdate }: UserProfileProps) {
  // Hooks first
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Effects next
  useEffect(() => {
    loadUser();
  }, [userId]);

  // Helper functions
  async function loadUser() {
    // Implementation
  }

  // Render
  return (
    <div>
      {/* Component JSX */}
    </div>
  );
}
```

### API Route Structure
```typescript
// app/api/users/route.ts

import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

// GET /api/users
export async function GET() {
  try {
    const users = await prisma.user.findMany();
    return NextResponse.json({ users });
  } catch (error) {
    console.error('Error fetching users:', error);
    return NextResponse.json(
      { error: 'Failed to fetch users' },
      { status: 500 }
    );
  }
}

// POST /api/users
export async function POST(request: Request) {
  try {
    const body = await request.json();
    // Validate input
    // Create user
    // Return response
  } catch (error) {
    console.error('Error creating user:', error);
    return NextResponse.json(
      { error: 'Failed to create user' },
      { status: 500 }
    );
  }
}
```

---

## Database Best Practices

### Prisma Schema Organization
```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// Models should be organized logically
// Add comments explaining relationships and business rules

// User authentication and profile
model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relations
  posts     Post[]

  @@index([email])
}

// Blog posts created by users
model Post {
  id        String   @id @default(cuid())
  title     String
  content   String
  published Boolean  @default(false)
  authorId  String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relations
  author    User     @relation(fields: [authorId], references: [id])

  @@index([authorId])
  @@index([published])
}
```

### Database Operations
- Use Prisma Client for all database operations (never raw SQL unless absolutely necessary)
- Always include error handling
- Use transactions for operations that must succeed or fail together
- Add indexes for fields used in WHERE clauses

---

## Testing Standards

### What to Test
Write tests for:
1. API endpoints (all routes)
2. Complex business logic functions
3. Data transformations
4. Form validation
5. Critical user flows

### Test Structure
```typescript
// __tests__/api/users.test.ts

import { GET, POST } from '@/app/api/users/route';

describe('Users API', () => {
  describe('GET /api/users', () => {
    it('should return list of users', async () => {
      const response = await GET();
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.users).toBeInstanceOf(Array);
    });

    it('should handle errors gracefully', async () => {
      // Test error case
    });
  });

  describe('POST /api/users', () => {
    it('should create a new user', async () => {
      // Test user creation
    });

    it('should validate required fields', async () => {
      // Test validation
    });
  });
});
```

### Testing Tools
- **Framework**: Jest or Vitest
- **React Testing**: React Testing Library
- **API Testing**: Supertest or direct Next.js handler calls

---

## Development Workflow

### Starting a New Feature
1. **Create a git branch** for the feature
2. **Write a plan** - outline what needs to be done
3. **Implement MVP** - get basic version working
4. **Test it** - verify it works as expected
5. **Refine** - improve code quality, add comments
6. **Document** - update README if needed
7. **Commit** - clear commit message
8. **Test again** - final verification

### Before Committing Code
Checklist before every commit:
- [ ] Code runs without errors
- [ ] Tests pass (if applicable)
- [ ] No console.log() left in code (unless intentional)
- [ ] TypeScript has no errors
- [ ] Comments added for complex logic
- [ ] Environment variables not hardcoded

---

## Naming Conventions

### Files
- **Components**: PascalCase - `UserProfile.tsx`
- **Utilities**: camelCase - `formatDate.ts`
- **API Routes**: lowercase - `route.ts` in folder `app/api/users/`
- **Types**: PascalCase - `User.ts` or in `types.ts`

### Variables & Functions
- **Variables**: camelCase - `const userName = 'John'`
- **Functions**: camelCase, verb-first - `getUserById()`, `handleSubmit()`
- **Constants**: UPPER_SNAKE_CASE - `const MAX_RETRIES = 3`
- **Components**: PascalCase - `function UserProfile() {}`
- **Interfaces**: PascalCase with descriptive names - `interface UserProfileProps {}`

### Database
- **Tables**: PascalCase, singular - `User`, `Post`
- **Fields**: camelCase - `createdAt`, `firstName`

---

## Code Review Questions

Before finalizing any code, ask yourself:
1. **Will I understand this code in 6 months?**
2. **Are errors handled properly?**
3. **Is this the simplest solution that works?**
4. **Are there any security risks?**
5. **Is it tested?**
6. **Is it documented?**

---

## When to Refactor

Refactor when:
- You notice repeated code (DRY principle)
- Functions are getting too long (>50 lines)
- Logic is hard to understand
- You're about to copy-paste code

Don't refactor when:
- The code works and is clear
- You're in the middle of getting an MVP working
- It would complicate things without clear benefit

---

## Performance Considerations

### General Rules
- Don't optimize prematurely - get it working first
- Use React's `useMemo` and `useCallback` only when needed
- Implement pagination for large lists
- Use database indexes for filtered/sorted fields
- Lazy load heavy components

### When Performance Matters
- Lists with 100+ items
- Heavy computations in components
- Large database queries
- File uploads/downloads
- Real-time features

---

## Learning Resources

When you need to learn more about a technology:
1. **Official docs first** - always start here
2. **Next.js docs**: [nextjs.org/docs](https://nextjs.org/docs)
3. **Prisma docs**: [prisma.io/docs](https://prisma.io/docs)
4. **React docs**: [react.dev](https://react.dev)
5. **TypeScript handbook**: [typescriptlang.org/docs/handbook](https://typescriptlang.org/docs/handbook)

Ask your AI assistant to explain concepts from these docs in simpler terms when needed.
