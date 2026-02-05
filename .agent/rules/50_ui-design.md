---
trigger: always_on
---

# 50_ui-design.md - UI Design & Frontend Standards

## Design Philosophy

### Core Principle
**Function over form.** Build interfaces that work well and are easy to use. Pretty designs are nice, but usability comes first.

### Priorities (in order)
1. **It works** - functionality is complete and bug-free
2. **It's clear** - users understand what to do
3. **It's accessible** - works for everyone, including screen readers
4. **It's responsive** - works on mobile and desktop
5. **It looks good** - polished and professional

---

## Styling with Tailwind CSS

### Why Tailwind
- No separate CSS files to manage
- Consistent spacing and colors
- Responsive design built-in
- Fast to write and iterate

### Basic Tailwind Patterns

#### Layout
```tsx
// Container with centered content
<div className="container mx-auto px-4">
  <div className="max-w-2xl mx-auto">
    {/* Content */}
  </div>
</div>

// Flexbox layouts
<div className="flex items-center justify-between">
  <div>Left side</div>
  <div>Right side</div>
</div>

// Grid layouts
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
</div>
```

#### Spacing
```tsx
// Padding: p-{size}
<div className="p-4">        {/* padding: 1rem (16px) */}
<div className="px-6 py-4">  {/* x=left/right, y=top/bottom */}
<div className="pt-2 pb-8">  {/* individual sides */}

// Margin: m-{size}
<div className="mt-4 mb-8">  {/* margin-top, margin-bottom */}

// Gap (for flex/grid)
<div className="flex gap-4"> {/* space between items */}
```

#### Sizing
```tsx
// Width
<div className="w-full">      {/* 100% */}
<div className="w-1/2">       {/* 50% */}
<div className="w-64">        {/* 256px */}
<div className="max-w-2xl">   {/* max-width: 42rem */}

// Height
<div className="h-screen">    {/* 100vh */}
<div className="min-h-screen"> {/* minimum 100vh */}
```

#### Colors
```tsx
// Background
<div className="bg-white">
<div className="bg-gray-100">
<div className="bg-blue-500">

// Text
<div className="text-gray-900">  {/* dark text */}
<div className="text-gray-600">  {/* muted text */}
<div className="text-blue-600">  {/* colored text */}

// Borders
<div className="border border-gray-300">
<div className="border-2 border-blue-500">
```

#### Typography
```tsx
// Size
<h1 className="text-4xl font-bold">      {/* large heading */}
<h2 className="text-2xl font-semibold">  {/* subheading */}
<p className="text-base">                {/* normal text */}
<p className="text-sm text-gray-600">    {/* small muted text */}

// Alignment
<div className="text-left">
<div className="text-center">
<div className="text-right">
```

### Responsive Design
Use breakpoint prefixes: `sm:`, `md:`, `lg:`, `xl:`

```tsx
// Stack on mobile, side-by-side on desktop
<div className="flex flex-col md:flex-row gap-4">
  <div className="w-full md:w-1/2">Left</div>
  <div className="w-full md:w-1/2">Right</div>
</div>

// Different text sizes
<h1 className="text-2xl md:text-4xl lg:text-5xl">
  Responsive Heading
</h1>

// Hide on mobile, show on desktop
<div className="hidden md:block">
  Desktop only content
</div>

// Show on mobile, hide on desktop
<div className="block md:hidden">
  Mobile only content
</div>
```

---

## Component Patterns

### Button Component
```tsx
// components/ui/Button.tsx

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

export default function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  type = 'button',
}: ButtonProps) {
  // Base styles for all buttons
  const baseStyles = "px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

  // Variant-specific styles
  const variants = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "bg-gray-200 text-gray-900 hover:bg-gray-300",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variants[variant]}`}
    >
      {children}
    </button>
  );
}

// Usage
<Button variant="primary">Save</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="danger">Delete</Button>
```

### Input Component
```tsx
// components/ui/Input.tsx

interface InputProps {
  label: string;
  type?: 'text' | 'email' | 'password' | 'number';
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  error?: string;
  required?: boolean;
}

export default function Input({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  required = false,
}: InputProps) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>

      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className={`
          w-full px-3 py-2 border rounded-lg
          focus:outline-none focus:ring-2 focus:ring-blue-500
          ${error ? 'border-red-500' : 'border-gray-300'}
        `}
      />

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

// Usage
<Input
  label="Email"
  type="email"
  value={email}
  onChange={setEmail}
  placeholder="you@example.com"
  required
  error={emailError}
/>
```

### Card Component
```tsx
// components/ui/Card.tsx

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export default function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`bg-white border border-gray-200 rounded-lg p-6 ${className}`}>
      {children}
    </div>
  );
}

// Usage
<Card>
  <h2 className="text-xl font-semibold mb-4">Card Title</h2>
  <p className="text-gray-600">Card content goes here.</p>
</Card>
```

### Loading Spinner
```tsx
// components/ui/Spinner.tsx

export default function Spinner() {
  return (
    <div className="flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  );
}

// Usage
{loading ? <Spinner /> : <Content />}
```

---

## Forms

### Basic Form Pattern
```tsx
'use client';

import { useState } from 'react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

export default function ContactForm() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function validateForm() {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }

    if (!formData.message.trim()) {
      newErrors.message = 'Message is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!validateForm()) return;

    setLoading(true);

    try {
      const response = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to submit form');
      }

      // Success - reset form
      setFormData({ name: '', email: '', message: '' });
      alert('Message sent successfully!');
    } catch (error) {
      console.error('Form submission error:', error);
      alert('Failed to send message. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
      <Input
        label="Name"
        value={formData.name}
        onChange={(value) => setFormData({ ...formData, name: value })}
        error={errors.name}
        required
      />

      <Input
        label="Email"
        type="email"
        value={formData.email}
        onChange={(value) => setFormData({ ...formData, email: value })}
        error={errors.email}
        required
      />

      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">
          Message <span className="text-red-500">*</span>
        </label>
        <textarea
          value={formData.message}
          onChange={(e) => setFormData({ ...formData, message: e.target.value })}
          rows={4}
          className={`
            w-full px-3 py-2 border rounded-lg
            focus:outline-none focus:ring-2 focus:ring-blue-500
            ${errors.message ? 'border-red-500' : 'border-gray-300'}
          `}
        />
        {errors.message && (
          <p className="text-sm text-red-600">{errors.message}</p>
        )}
      </div>

      <Button type="submit" disabled={loading}>
        {loading ? 'Sending...' : 'Send Message'}
      </Button>
    </form>
  );
}
```

---

## Accessibility Guidelines

### Always Include
1. **Semantic HTML**: Use correct elements (`<button>`, `<nav>`, `<main>`, etc.)
2. **Alt text**: Every image needs descriptive alt text
3. **Labels**: Every form input needs a label
4. **Keyboard navigation**: All interactive elements must be keyboard accessible
5. **Focus indicators**: Visible focus states (`:focus` styles)

### Examples
```tsx
// ✅ Good - semantic HTML, alt text, label
<button onClick={handleClick}>Click me</button>
<img src="/logo.png" alt="Company logo" />
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// ❌ Bad - div as button, no alt, no label
<div onClick={handleClick}>Click me</div>
<img src="/logo.png" />
<input type="email" />
```

### Color Contrast
- Text should have sufficient contrast with background
- Use dark text on light backgrounds, or vice versa
- Tools: [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

---

## Mobile-First Design

### Design for Mobile First
Start with mobile layout, then enhance for desktop.

```tsx
// ✅ Mobile-first approach
<div className="
  flex flex-col        // Stack vertically on mobile
  md:flex-row          // Side-by-side on tablet+
  gap-4                // 1rem gap
  p-4                  // 1rem padding
  md:p-8               // 2rem padding on tablet+
">
  <div className="w-full md:w-1/2">Content 1</div>
  <div className="w-full md:w-1/2">Content 2</div>
</div>
```

### Touch Targets
Make buttons and links large enough to tap on mobile (minimum 44x44px).

```tsx
// ✅ Good - large enough touch target
<button className="px-4 py-3 text-base">
  Tap me
</button>

// ❌ Bad - too small
<button className="px-1 py-1 text-xs">
  Tap me
</button>
```

---

## Loading States

### Show Loading Indicators
Always show feedback when something is loading.

```tsx
export default function DataDisplay() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const response = await fetch('/api/data');
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError('Failed to load data');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-red-600">
        {error}
      </div>
    );
  }

  return (
    <div>
      {/* Display data */}
    </div>
  );
}
```

---

## Error States

### User-Friendly Error Messages
```tsx
// ❌ Bad - technical error message
<p>Error: ECONNREFUSED 127.0.0.1:5432</p>

// ✅ Good - user-friendly message
<p>Unable to connect to the database. Please try again later.</p>
```

### Error Display Pattern
```tsx
{error && (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
    <p className="text-red-800 font-medium">Something went wrong</p>
    <p className="text-red-600 text-sm mt-1">{error}</p>
  </div>
)}
```

---

## Common UI Patterns

### Navigation Bar
```tsx
// components/Navbar.tsx

export default function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="/" className="text-xl font-bold text-gray-900">
            MyApp
          </a>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-8">
            <a href="/features" className="text-gray-600 hover:text-gray-900">
              Features
            </a>
            <a href="/pricing" className="text-gray-600 hover:text-gray-900">
              Pricing
            </a>
            <a href="/about" className="text-gray-600 hover:text-gray-900">
              About
            </a>
          </div>

          {/* CTA Button */}
          <Button variant="primary">Sign In</Button>
        </div>
      </div>
    </nav>
  );
}
```

### Footer
```tsx
// components/Footer.tsx

export default function Footer() {
  return (
    <footer className="bg-gray-50 border-t border-gray-200 mt-auto">
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Company Info */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">MyApp</h3>
            <p className="text-gray-600 text-sm">
              Building amazing web applications.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Links</h3>
            <ul className="space-y-2">
              <li><a href="/about" className="text-gray-600 hover:text-gray-900 text-sm">About</a></li>
              <li><a href="/contact" className="text-gray-600 hover:text-gray-900 text-sm">Contact</a></li>
              <li><a href="/privacy" className="text-gray-600 hover:text-gray-900 text-sm">Privacy</a></li>
            </ul>
          </div>

          {/* Copyright */}
          <div>
            <p className="text-gray-600 text-sm">
              © {new Date().getFullYear()} MyApp. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
```

---

## Design Checklist

Before considering UI "done":

### Functionality
- [ ] All buttons and links work
- [ ] Forms submit successfully
- [ ] Validation works correctly
- [ ] Error states display properly
- [ ] Loading states show while waiting

### Responsiveness
- [ ] Looks good on mobile (375px width)
- [ ] Looks good on tablet (768px width)
- [ ] Looks good on desktop (1440px width)
- [ ] Text is readable on all screen sizes
- [ ] Touch targets are large enough on mobile

### Accessibility
- [ ] All images have alt text
- [ ] All inputs have labels
- [ ] Can navigate with keyboard only
- [ ] Focus states are visible
- [ ] Color contrast is sufficient

### Polish
- [ ] Consistent spacing
- [ ] Consistent colors
- [ ] Consistent typography
- [ ] No console errors
- [ ] No layout shifts when loading

---

## When Design Doesn't Matter Much

For personal/learning projects, it's okay to keep design minimal:
- Use default Tailwind classes
- Focus on functionality
- Use simple layouts
- Don't spend hours on pixel-perfect design

**Remember**: A functional ugly app is better than a beautiful broken app.

---

## Design Resources

### Inspiration
- [Tailwind UI](https://tailwindui.com/) - Component examples (some free)
- [Shadcn UI](https://ui.shadcn.com/) - Copy-paste components
- [Flowbite](https://flowbite.com/) - Free Tailwind components

### Tools
- [Tailwind CSS Docs](https://tailwindcss.com/docs) - Official documentation
- [Heroicons](https://heroicons.com/) - Free SVG icons
- [Google Fonts](https://fonts.google.com/) - Free fonts

### Colors
- Stick with Tailwind's default color palette
- Use gray for neutral elements
- Pick one primary color (blue, green, purple, etc.)
- Use red for errors, green for success, yellow for warnings

---

## Final Thoughts

Good UI design is:
1. **Clear** - Users know what to do
2. **Consistent** - Similar things look similar
3. **Responsive** - Works on all devices
4. **Accessible** - Works for everyone
5. **Fast** - No unnecessary delays

Don't overthink it. Start simple, test on real devices, and iterate based on what works.
