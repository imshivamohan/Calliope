<script lang="ts">
	/**
	 * ShotBrief — the selected clip's production brief in the Video composer.
	 *
	 * Clips are render units: each performs one beat of a scene. Without this
	 * panel the per-clip content (what the camera sees, the shot size, the
	 * dialog lines it carries) was only visible in the monitor's empty state —
	 * truncated, and gone as soon as a render existed. Surfacing it here is
	 * what tells a user what to write into the workflow's prompt field.
	 */
	import type { Clip, Scene } from '$lib/api';
	import Icon from '$lib/components/ui/Icon.svelte';
	import { t } from '$lib/i18n.svelte';

	interface Props {
		clip: Clip;
		scene: Scene;
		/** Display label, e.g. '#3.2'. */
		label: string;
		formatClock: (sec: number) => string;
	}

	let { clip, scene, label, formatClock }: Props = $props();

	let open = $state(false);
	let copied = $state(false);
	let copiedDialog = $state(false);
	let copyTimer: ReturnType<typeof setTimeout> | null = null;
	let copyDialogTimer: ReturnType<typeof setTimeout> | null = null;

	const description = $derived((clip.description ?? '').trim());
	/** Un-expanded (legacy) clips carry no per-shot description — fall back to the scene action. */
	const sceneLevel = $derived(!description && Boolean((scene.action ?? '').trim()));
	const body = $derived(description || (scene.action ?? '').trim());

	/** Same contract as the backend's `_clip_dialog`: 1-based indexes into the non-empty dialog lines. */
	const coveredLines = $derived.by(() => {
		const covered = clip.dialog_lines_covered;
		if (!covered || covered.length === 0) return [];
		const lines = (scene.dialog ?? '').split(/\r?\n/).filter((l) => l.trim());
		return covered
			.filter((i) => Number.isInteger(i) && i >= 1 && i <= lines.length)
			.map((i) => lines[i - 1]);
	});

	const shotSizeLabel = $derived(
		clip.shot_size ? clip.shot_size.replace(/([A-Z])/g, ' $1').trim() : '',
	);

	/** Combined text: visual action prompt + dialog lines if present. */
	const combinedText = $derived.by(() => {
		const parts: string[] = [];
		if (body) parts.push(body);
		if (coveredLines.length > 0) {
			parts.push(coveredLines.join('\n'));
		}
		return parts.join('\n\n');
	});

	async function copyCombined() {
		if (!combinedText) return;
		try {
			await navigator.clipboard.writeText(combinedText);
			copied = true;
			if (copyTimer) clearTimeout(copyTimer);
			copyTimer = setTimeout(() => (copied = false), 1500);
		} catch {
			/* clipboard blocked (insecure context) — leave the button as-is */
		}
	}

	async function copyDialogOnly() {
		if (coveredLines.length === 0) return;
		try {
			await navigator.clipboard.writeText(coveredLines.join('\n'));
			copiedDialog = true;
			if (copyDialogTimer) clearTimeout(copyDialogTimer);
			copyDialogTimer = setTimeout(() => (copiedDialog = false), 1500);
		} catch {
			/* clipboard blocked */
		}
	}
</script>

<div class="brief">
	<div class="head">
		<span class="label mono">{label}</span>
		{#if shotSizeLabel}
			<span class="pill">{shotSizeLabel}</span>
		{/if}
		<span class="dur mono">{formatClock(clip.duration_sec || 5)}</span>
		<span class="grow"></span>
		<button
			type="button"
			class="icon-btn"
			disabled={!combinedText}
			title={copied
				? t('shotBrief.copied')
				: coveredLines.length > 0
					? t('shotBrief.copyCombinedTitle')
					: t('shotBrief.copyTitle')}
			aria-label={coveredLines.length > 0 ? t('shotBrief.copyCombinedTitle') : t('shotBrief.copyTitle')}
			onclick={copyCombined}
		>
			<Icon name={copied ? 'check' : 'copy'} size={13} />
			<span class="icon-btn-text">{copied ? t('shotBrief.copied') : t('shotBrief.copy')}</span>
		</button>
		<button
			type="button"
			class="icon-btn"
			class:open
			aria-expanded={open}
			title={open ? t('shotBrief.collapse') : t('shotBrief.expand')}
			onclick={() => (open = !open)}
		>
			<Icon name={open ? 'chevron-up' : 'chevron-down'} size={13} />
		</button>
	</div>

	<p class="desc" class:clamped={!open}>
		{#if body}
			{body}
		{:else}
			<span class="muted">{t('shotBrief.noDesc')}</span>
		{/if}
	</p>

	{#if open}
		{#if sceneLevel}
			<p class="note">
				{t('shotBrief.notePre')}
				<span class="mono">{t('shotBrief.breakIntoShots')}</span>
				{t('shotBrief.notePost')}
			</p>
		{/if}

		{#if coveredLines.length}
			<div class="block">
				<div class="block-header">
					<span class="k">{t('shotBrief.dialogKey')}</span>
					<button
						type="button"
						class="mini-copy-btn"
						title={copiedDialog ? t('shotBrief.copied') : t('shotBrief.copyDialogTitle')}
						onclick={copyDialogOnly}
					>
						<Icon name={copiedDialog ? 'check' : 'copy'} size={11} />
						<span>{copiedDialog ? t('shotBrief.copied') : t('shotBrief.copy')}</span>
					</button>
				</div>
				<pre class="dialog">{coveredLines.join('\n')}</pre>
			</div>
		{/if}

		{#if (scene.characters ?? []).length}
			<div class="block">
				<span class="k">{t('shotBrief.characters')}</span>
				<div class="chips">
					{#each scene.characters as c (c.id)}
						<span class="chip">{c.name}</span>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	.brief {
		flex-shrink: 0;
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		background: var(--bg-surface);
		padding: 8px 10px;
		margin: 0;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 20px;
	}

	.label {
		font-size: 12px;
		font-weight: 700;
		color: var(--accent);
		flex-shrink: 0;
	}

	.pill {
		padding: 1px 8px;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--bg-elevated);
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-secondary);
		flex-shrink: 0;
	}

	.dur {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-muted);
		flex-shrink: 0;
	}

	.grow {
		flex: 1;
		min-width: 0;
	}

	.icon-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 24px;
		padding: 0 8px;
		font: inherit;
		font-size: 11px;
		font-weight: 600;
		color: var(--text-secondary);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
		flex-shrink: 0;
	}

	.icon-btn:hover:not(:disabled),
	.icon-btn.open {
		color: var(--text-primary);
		border-color: var(--text-muted);
	}

	.icon-btn:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.icon-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.icon-btn-text {
		line-height: 1;
	}

	.desc {
		margin: 6px 0 0;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--text-secondary);
		white-space: pre-wrap;
		word-break: break-word;
	}

	.desc.clamped {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.muted {
		color: var(--text-muted);
	}

	.note {
		margin: 8px 0 0;
		font-size: 11.5px;
		line-height: 1.45;
		color: var(--text-muted);
	}

	.block {
		margin-top: 8px;
	}

	.block-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 4px;
	}

	.block .k {
		display: block;
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	.mini-copy-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		padding: 2px 7px;
		border-radius: var(--radius-sm);
		font-size: 10px;
		font-weight: 600;
		color: var(--text-secondary);
		cursor: pointer;
		line-height: 1;
		transition: color 0.15s, border-color 0.15s;
	}

	.mini-copy-btn:hover {
		color: var(--text-primary);
		border-color: var(--text-muted);
	}

	.dialog {
		margin: 0;
		padding: 6px 8px;
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		font-family: var(--font-mono);
		font-size: 11.5px;
		line-height: 1.45;
		white-space: pre-wrap;
		color: var(--text-primary);
		max-height: 90px;
		overflow-y: auto;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.chip {
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 1px 9px;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.mono {
		font-family: var(--font-mono);
	}
</style>
