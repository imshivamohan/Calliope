# Calliope Internationalization (i18n) & UI Architecture

Calliope 1.5.2+ includes a fully localized 7-language UI and an SSR-hardened client storage layer.

---

## 1. Seven-Language Localization (i18n)

Every user-facing string in the interface is resolved through a typed dictionary system.

### Supported Languages
1. **English** (`en`) — Source of truth
2. **Chinese / 中文** (`zh`)
3. **Spanish / Español** (`es`)
4. **French / Français** (`fr`)
5. **German / Deutsch** (`de`)
6. **Japanese / 日本語** (`ja`)
7. **Korean / 한국어** (`ko`)

### Type Safety & Completeness Guarantee
- Location: `calliope-web/src/lib/i18n/`
- Every language dictionary is strictly typed against `type Dict = typeof en`.
- If any translation file is missing even one of the 1,000+ dictionary keys, TypeScript compile (`npm run check` or `vite build`) immediately fails with a type error.
- **Language Switcher**: Located in the application header (`AppHeader.svelte` / `LanguageSwitcher.svelte`). Persists selection in `localStorage` under `calliope-lang`.

### Interpolation & Pluralization Syntax
The `t(key, params)` helper supports dynamic placeholder substitution:
```svelte
<!-- Simple interpolation -->
<p>{t('projects.created_by', { name: author })}</p>

<!-- Count shorthand (populates both {count} and {n}) -->
<span>{t('queue.items_remaining', { count: remaining })}</span>
```

### Stored Database Enum Mapping
Narrative settings like **Genre**, **Tone**, and **Target Duration** are stored in SQLite using stable English values. `calliope-web/src/lib/formOptions.ts` maps these English database identifiers to localized dictionary strings, ensuring data portability across different user languages.

---

## 2. Server-Side Rendering (SSR) Storage Guard (`lib/storage.ts`)

### The Node 22+ Storage Crash
Node.js 22+ introduces a global `localStorage` binding. However, when run under server environments without an active `--localstorage-file`, this global is an object lacking standard Storage prototype methods. A conventional check like `if (typeof localStorage !== 'undefined')` evaluates to true, but calling `localStorage.getItem()` throws `TypeError: localStorage.getItem is not a function`, crashing SSR.

### The Solution: Method Probing
`calliope-web/src/lib/storage.ts` wraps all web storage calls with explicit callable probing:
```ts
export function safeGetItem(key: string): string | null {
  try {
    if (typeof window !== 'undefined' && typeof window.localStorage?.getItem === 'function') {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Storage access disabled or sandboxed
  }
  return null;
}
```

### Verification
Run `npm test` inside `calliope-web` to execute `scripts/check-storage-ssr.mjs`, validating that the client storage abstraction functions safely in both browser and headless Node SSR contexts.

---

## 3. UI Component Architecture

The frontend is constructed with Svelte 5 runes (`$state`, `$derived`, `$props`) and TailwindCSS:
- **`NavRail.svelte`**: Persistent left navigation rail linking Projects, Canvas, Build Scene, Playground, Library, and Settings.
- **`AppHeader.svelte`**: Breadcrumbs, ComfyUI/LLM connection indicators, Language switcher.
- **`SafeMedia.svelte`**: Universal media wrapper with auto-retry, mime-type detection, and graceful placeholder rendering for missing assets.
- **`ComfyDynamicForm.svelte`**: Generates form inputs dynamically from discovered workflow role tags.
- **`ToastHost.svelte`**: Global non-blocking status notifications.
