---
trigger: always_on
---

# 60_backend-admin.md - Backend Logic & Admin Panels

## Backend Architecture in Next.js

### Understanding Next.js Backend Structure
Next.js handles both frontend AND backend in one framework. Your backend code lives in:
- **API Routes**: `app/api/*/route.ts` - Traditional REST endpoints
- **Server Actions**: Functions that run on the server, called from components
- **Server Components**: React components that fetch data on the server

---

## Organizing Complex Backend Logic

### The Problem
When business logic gets complex, putting everything in API routes becomes messy:

```typescript
// ❌ Bad - Everything in the API route (gets messy fast)
export async function POST(request: Request) {
  const body = await request.json();

  // 50 lines of validation logic
  // 100 lines of business logic
  // 30 lines of database operations
  // 20 lines of email sending

  return NextResponse.json({ result });
}
```

### The Solution: Service Layer Pattern

Organize backend logic into separate, reusable service files:

```
app/
├── api/
│   └── users/
│       └── route.ts          # Thin controller (receives request, returns response)
└── services/
    ├── userService.ts        # Business logic for users
    ├── emailService.ts       # Email operations
    └── authService.ts        # Authentication logic
```

---

## Service Layer Pattern

### What is a Service?
A service is a file containing related business logic functions. It separates "what to do" from "how to handle HTTP requests."

### Example: User Service

```typescript
// app/services/userService.ts

import { prisma } from '@/lib/db';
import { hash } from 'bcryptjs';

/**
 * User-related business logic
 * All functions here are reusable across API routes, server actions, etc.
 */

export interface CreateUserData {
  email: string;
  password: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
}

/**
 * Creates a new user with hashed password
 * Validates that email doesn't already exist
 *
 * @throws Error if email already exists
 * @throws Error if password is too weak
 */
export async function createUser(data: CreateUserData): Promise<User> {
  // Business logic: Check if user exists
  const existingUser = await prisma.user.findUnique({
    where: { email: data.email },
  });

  if (existingUser) {
    throw new Error('User with this email already exists');
  }

  // Business logic: Validate password strength
  if (data.password.length < 8) {
    throw new Error('Password must be at least 8 characters');
  }

  // Business logic: Hash password
  const hashedPassword = await hash(data.password, 10);

  // Database operation: Create user
  const user = await prisma.user.create({
    data: {
      email: data.email,
      name: data.name,
      password: hashedPassword,
    },
  });

  // Return user (without password)
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    createdAt: user.createdAt,
  };
}

/**
 * Gets a user by ID
 *
 * @throws Error if user not found
 */
export async function getUserById(id: string): Promise<User> {
  const user = await prisma.user.findUnique({
    where: { id },
  });

  if (!user) {
    throw new Error('User not found');
  }

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    createdAt: user.createdAt,
  };
}

/**
 * Updates user profile information
 *
 * @throws Error if user not found
 */
export async function updateUser(
  id: string,
  data: { name?: string; email?: string }
): Promise<User> {
  // Business logic: Validate at least one field is being updated
  if (!data.name && !data.email) {
    throw new Error('No fields to update');
  }

  // Business logic: If email is changing, check it's not taken
  if (data.email) {
    const existingUser = await prisma.user.findUnique({
      where: { email: data.email },
    });

    if (existingUser && existingUser.id !== id) {
      throw new Error('Email already in use');
    }
  }

  // Database operation: Update user
  const user = await prisma.user.update({
    where: { id },
    data,
  });

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    createdAt: user.createdAt,
  };
}

/**
 * Deletes a user and all their related data
 * This is a complex operation that needs to be handled carefully
 */
export async function deleteUser(id: string): Promise<void> {
  // Business logic: Use a transaction to ensure all-or-nothing deletion
  await prisma.$transaction(async (tx) => {
    // Delete user's posts first (foreign key constraint)
    await tx.post.deleteMany({
      where: { authorId: id },
    });

    // Then delete the user
    await tx.user.delete({
      where: { id },
    });
  });
}
```

### Using the Service in API Routes

```typescript
// app/api/users/route.ts

import { NextResponse } from 'next/server';
import { createUser } from '@/app/services/userService';
import { z } from 'zod';

// Validation schema
const createUserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1),
});

/**
 * POST /api/users
 * Creates a new user
 */
export async function POST(request: Request) {
  try {
    // 1. Parse and validate input
    const body = await request.json();
    const validatedData = createUserSchema.parse(body);

    // 2. Call service function (business logic)
    const user = await createUser(validatedData);

    // 3. Return response
    return NextResponse.json(
      { user },
      { status: 201 }
    );
  } catch (error) {
    // Handle validation errors
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }

    // Handle business logic errors
    if (error instanceof Error) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 }
      );
    }

    // Handle unexpected errors
    console.error('Unexpected error creating user:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

---

## When to Use Services

### Use Services When:
- ✅ Logic is used in multiple places (API routes, server actions, cron jobs)
- ✅ Business logic is complex (more than 20-30 lines)
- ✅ You need to test the logic independently
- ✅ The operation involves multiple steps or database operations

### Keep it Simple When:
- ❌ It's a simple CRUD operation (create/read/update/delete)
- ❌ The logic is only used once
- ❌ It's just a thin wrapper around a database call

### Example: When NOT to use a service

```typescript
// app/api/posts/[id]/route.ts

// ✅ This is simple enough - no service needed
export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const post = await prisma.post.findUnique({
      where: { id: params.id },
      include: { author: true },
    });

    if (!post) {
      return NextResponse.json(
        { error: 'Post not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({ post });
  } catch (error) {
    console.error('Error fetching post:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

---

## Complex Business Logic Examples

### Example 1: Order Processing Service

```typescript
// app/services/orderService.ts

import { prisma } from '@/lib/db';
import { sendEmail } from './emailService';
import { processPayment } from './paymentService';

export interface CreateOrderData {
  userId: string;
  items: Array<{
    productId: string;
    quantity: number;
  }>;
  paymentMethodId: string;
}

/**
 * Creates an order with payment processing
 * This is complex business logic that coordinates multiple operations
 */
export async function createOrder(data: CreateOrderData) {
  // Use a transaction - either everything succeeds or everything fails
  return await prisma.$transaction(async (tx) => {
    // 1. Get products and validate availability
    const products = await tx.product.findMany({
      where: {
        id: { in: data.items.map(item => item.productId) },
      },
    });

    // Validate all products exist
    if (products.length !== data.items.length) {
      throw new Error('Some products not found');
    }

    // 2. Calculate total amount
    let totalAmount = 0;
    for (const item of data.items) {
      const product = products.find(p => p.id === item.productId);
      if (!product) continue;

      // Check stock availability
      if (product.stock < item.quantity) {
        throw new Error(`Insufficient stock for ${product.name}`);
      }

      totalAmount += product.price * item.quantity;
    }

    // 3. Process payment (external service)
    const payment = await processPayment({
      amount: totalAmount,
      paymentMethodId: data.paymentMethodId,
    });

    if (!payment.success) {
      throw new Error('Payment failed: ' + payment.error);
    }

    // 4. Create order in database
    const order = await tx.order.create({
      data: {
        userId: data.userId,
        totalAmount,
        status: 'PAID',
        paymentId: payment.id,
        items: {
          create: data.items.map(item => ({
            productId: item.productId,
            quantity: item.quantity,
            price: products.find(p => p.id === item.productId)!.price,
          })),
        },
      },
      include: {
        items: {
          include: {
            product: true,
          },
        },
      },
    });

    // 5. Update product stock
    for (const item of data.items) {
      await tx.product.update({
        where: { id: item.productId },
        data: {
          stock: {
            decrement: item.quantity,
          },
        },
      });
    }

    // 6. Send confirmation email (don't await - let it happen in background)
    sendEmail({
      to: data.userId,
      subject: 'Order Confirmation',
      template: 'order-confirmation',
      data: { order },
    }).catch(error => {
      console.error('Failed to send order confirmation:', error);
      // Don't throw - email failure shouldn't fail the order
    });

    return order;
  });
}
```

### Example 2: Report Generation Service

```typescript
// app/services/reportService.ts

import { prisma } from '@/lib/db';

export interface SalesReport {
  period: string;
  totalRevenue: number;
  totalOrders: number;
  averageOrderValue: number;
  topProducts: Array<{
    productId: string;
    productName: string;
    quantitySold: number;
    revenue: number;
  }>;
}

/**
 * Generates a sales report for a given date range
 * Complex aggregation logic
 */
export async function generateSalesReport(
  startDate: Date,
  endDate: Date
): Promise<SalesReport> {
  // Run multiple queries in parallel for better performance
  const [orders, orderItems] = await Promise.all([
    // Get all orders in date range
    prisma.order.findMany({
      where: {
        createdAt: {
          gte: startDate,
          lte: endDate,
        },
        status: 'PAID',
      },
      select: {
        totalAmount: true,
      },
    }),

    // Get all order items with product info
    prisma.orderItem.findMany({
      where: {
        order: {
          createdAt: {
            gte: startDate,
            lte: endDate,
          },
          status: 'PAID',
        },
      },
      include: {
        product: true,
      },
    }),
  ]);

  // Calculate totals
  const totalRevenue = orders.reduce((sum, order) => sum + order.totalAmount, 0);
  const totalOrders = orders.length;
  const averageOrderValue = totalOrders > 0 ? totalRevenue / totalOrders : 0;

  // Calculate top products
  const productStats = new Map<string, {
    name: string;
    quantity: number;
    revenue: number;
  }>();

  for (const item of orderItems) {
    const existing = productStats.get(item.productId);
    const revenue = item.price * item.quantity;

    if (existing) {
      existing.quantity += item.quantity;
      existing.revenue += revenue;
    } else {
      productStats.set(item.productId, {
        name: item.product.name,
        quantity: item.quantity,
        revenue,
      });
    }
  }

  // Sort and get top 10
  const topProducts = Array.from(productStats.entries())
    .map(([productId, stats]) => ({
      productId,
      productName: stats.name,
      quantitySold: stats.quantity,
      revenue: stats.revenue,
    }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 10);

  return {
    period: `${startDate.toISOString()} to ${endDate.toISOString()}`,
    totalRevenue,
    totalOrders,
    averageOrderValue,
    topProducts,
  };
}
```

---

## Admin Panels

### The Challenge
Most applications need an admin interface to:
- Manage users
- View/edit database records
- Generate reports
- Configure settings
- Monitor system health

Building a full admin panel from scratch is a LOT of work.

---

## Admin Panel Solutions

### Option 1: Next.js Admin (React Admin)
**Best for**: Learning and full control

```bash
npm install react-admin ra-data-simple-rest
```

**Pros**:
- TypeScript-first
- Works directly with Next.js
- Good documentation
- Active community

**Cons**:
- More setup required
- Need to build data provider

**Example**:
```typescript
// app/admin/page.tsx
'use client';

import { Admin, Resource, ListGuesser } from 'react-admin';
import simpleRestProvider from 'ra-data-simple-rest';

const dataProvider = simpleRestProvider('/api');

export default function AdminApp() {
  return (
    <Admin dataProvider={dataProvider}>
      <Resource name="users" list={ListGuesser} />
      <Resource name="posts" list={ListGuesser} />
      <Resource name="orders" list={ListGuesser} />
    </Admin>
  );
}
```

### Option 2: Refine
**Best for**: Modern TypeScript apps

```bash
npm install @refinedev/core @refinedev/nextjs-router
```

**Pros**:
- Excellent TypeScript support
- Very flexible
- Great with Next.js
- Modern architecture

**Cons**:
- Steeper learning curve
- Requires more configuration

**When to use**: When you need a production-grade admin panel and want type safety.

### Option 3: Build Custom Admin
**Best for**: Simple needs, learning

Build your own admin using your existing components:

```
app/
├── admin/
│   ├── layout.tsx          # Admin layout with sidebar
│   ├── page.tsx            # Admin dashboard
│   ├── users/
│   │   ├── page.tsx        # List users
│   │   └── [id]/
│   │       └── page.tsx    # Edit user
│   └── posts/
│       ├── page.tsx        # List posts
│       └── [id]/
│           └── page.tsx    # Edit post
```

**Example: Simple Admin List Page**:
```typescript
// app/admin/users/page.tsx

import { prisma } from '@/lib/db';
import Link from 'next/link';

export default async function UsersAdminPage() {
  // Fetch users on server
  const users = await prisma.user.findMany({
    orderBy: { createdAt: 'desc' },
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Users</h1>
        <Link
          href="/admin/users/new"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg"
        >
          Add User
        </Link>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 text-left text-sm font-semibold">Name</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Email</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Created</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b">
                <td className="px-6 py-4">{user.name}</td>
                <td className="px-6 py-4">{user.email}</td>
                <td className="px-6 py-4">
                  {new Date(user.createdAt).toLocaleDateString()}
                </td>
                <td className="px-6 py-4">
                  <Link
                    href={`/admin/users/${user.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    Edit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### Option 4: Headless CMS (Payload CMS)
**Best for**: Content-heavy applications

If your app is mainly about managing content (blogs, products, etc.):

```bash
npx create-payload-app@latest
```

**Pros**:
- Complete admin UI out of the box
- Built-in authentication
- Rich text editor
- Media management
- Works with Next.js

**Cons**:
- Adds complexity
- Less flexible for custom business logic

**When to use**: Building a CMS, e-commerce site, or content-heavy app.

---

## Recommendation for Your Level

### Start Simple: Build Custom Admin
For your first few projects:
1. Build a simple custom admin using Next.js pages
2. Use your existing UI components
3. Focus on CRUD operations (Create, Read, Update, Delete)
4. This teaches you the fundamentals

### When to Upgrade
Move to React Admin or Refine when:
- You have 5+ database tables to manage
- You need complex filtering/sorting
- You want to move faster
- The project is becoming production-grade

---

## Admin Panel Checklist

### Essential Features
- [ ] Authentication (admin-only access)
- [ ] User management (list, create, edit, delete)
- [ ] Content management (posts, products, etc.)
- [ ] Basic dashboard (stats, recent activity)
- [ ] Search and filtering

### Nice-to-Have Features
- [ ] Bulk operations
- [ ] Export to CSV
- [ ] Activity logs
- [ ] Role-based permissions
- [ ] Advanced reporting

### Security Requirements
- [ ] Require authentication for ALL admin routes
- [ ] Check user role/permissions
- [ ] Audit log important actions
- [ ] Rate limiting on admin actions
- [ ] CSRF protection

---

## Protecting Admin Routes

```typescript
// app/admin/layout.tsx

import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Check if user is authenticated
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/login?callbackUrl=/admin');
  }

  // Check if user is admin
  if (session.user.role !== 'admin') {
    redirect('/');
  }

  return (
    <div className="flex min-h-screen">
      {/* Admin Sidebar */}
      <aside className="w-64 bg-gray-900 text-white p-6">
        <h2 className="text-xl font-bold mb-6">Admin Panel</h2>
        <nav className="space-y-2">
          <a href="/admin" className="block py-2 px-4 rounded hover:bg-gray-800">
            Dashboard
          </a>
          <a href="/admin/users" className="block py-2 px-4 rounded hover:bg-gray-800">
            Users
          </a>
          <a href="/admin/posts" className="block py-2 px-4 rounded hover:bg-gray-800">
            Posts
          </a>
        </nav>
      </aside>

      {/* Admin Content */}
      <main className="flex-1 bg-gray-50">
        {children}
      </main>
    </div>
  );
}
```

---

## Summary: Backend & Admin Strategy

### For Backend Logic:
1. **Start simple**: Put logic in API routes
2. **Extract to services**: When logic gets complex or is reused
3. **Use transactions**: For operations that must all succeed or all fail
4. **Document well**: Complex logic needs good comments
5. **Test thoroughly**: Backend bugs are harder to catch

### For Admin Panels:
1. **Phase 1 (Learning)**: Build custom admin with Next.js
2. **Phase 2 (Growing)**: Consider React Admin or Refine
3. **Phase 3 (Scaling)**: Add advanced features as needed

### The Progressive Approach:
```
Simple CRUD → Services → Admin UI → Advanced Features
```

Start with what you need, add complexity only when you feel it.

---

## Questions to Ask Your AI

When building backend features:
- "Should this logic be in a service or is the API route fine?"
- "How do I structure this complex operation?"
- "What error cases do I need to handle?"
- "Do I need a database transaction here?"

When building admin:
- "Should I build custom or use a library?"
- "How do I protect admin routes?"
- "What's the best way to display this data?"
- "How do I handle pagination?"

Your AI will help you make the right choice for your current skill level and project needs.
