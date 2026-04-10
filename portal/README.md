# Portal

Two Next.js applications sharing a component library.

## factory_portal/
Layer 1: Forge Factory Portal — commission employees, track builds, manage roster, billing.
- Auth: Clerk
- Stack: Next.js 15 + shadcn/ui + Tailwind

## employee_app/
Layer 2: The Employee App — daily interaction interface.
- Conversation (80%): rich chat, inline actions, approval cards
- Sidebar (20%): Inbox, Activity, Documents, Memory, Settings, Updates, Metrics
- Desktop: wrapped with Electron via electron-builder → .dmg / .exe / .AppImage

## Getting started
```bash
cd portal/factory_portal && npm install && npm run dev   # :3000
cd portal/employee_app   && npm install && npm run dev   # :3001
```
