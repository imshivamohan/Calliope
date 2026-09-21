<script lang="ts">
	/**
	 * ShotBrief — the selected clip's production brief in the Video composer.
	 *
	 * Displays shot details, action prompt, audio dialogue playback,
	 * voice cloning/TTS controls with reference vs default presets,
	 * and quick copy & paste buttons.
	 */
	import { assetUrl, projects, type Clip, type Scene } from '$lib/api';
	import { useQueryClient } from '@tanstack/svelte-query';
	import { toast } from '$lib/toast';
	import Icon from '$lib/components/ui/Icon.svelte';
	import { t } from '$lib/i18n.svelte';

	interface Props {
		clip: Clip;
		scene: Scene;
		/** Display label, e.g. '#3.2'. */
		label: string;
		formatClock: (sec: number) => string;
		projectId?: number;
		onPastePrompt?: (text: string) => void;
	}

	let { clip, scene, label, formatClock, projectId, onPastePrompt }: Props = $props();
	const client = useQueryClient();

	let open = $state(false);
	let copied = $state(false);
	let pasted = $state(false);
	let copyTimer: ReturnType<typeof setTimeout> | null = null;
	let pasteTimer: ReturnType<typeof setTimeout> | null = null;

	let voiceEngine = $state<'higgs' | 'fish'>('higgs');
	let voiceOption = $state<'reference' | 'female' | 'male'>('reference');
	let enhanced = $state(true);
	let generatingVoice = $state(false);

	async function generateVoice() {
		if (!projectId) return;
		generatingVoice = true;
		try {
			await projects.generateClipVoice(projectId, clip.id, {
				engine: voiceEngine,
				voice_option: voiceOption,
				enhanced,
			});
			const voiceName =
				voiceOption === 'male'
					? 'Default Male'
					: voiceOption === 'female'
						? 'Default Female'
						: 'Character Reference';
			toast.success(`Voice generation queued (${voiceName})`);
			await client.invalidateQueries({ queryKey: ['project', projectId] });
			await client.invalidateQueries({ queryKey: ['jobs', projectId] });
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Failed to queue voice generation');
		} finally {
			generatingVoice = false;
		}
	}

	const description = $derived((clip.description ?? '').trim());
	/** Un-expanded (legacy) clips carry no per-shot description — fall back to the scene action. */
	const sceneLevel = $derived(!description && Boolean((scene.action ?? '').trim()));
	const body = $derived(description || (scene.action ?? '').trim());

	function parseScreenplayTurns(rawText: string | null | undefined): string[] {
		if (!rawText) return [];
		const rawLines = rawText.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
		const turns: string[] = [];
		let currentSpeaker = '';
		let currentCue = '';
		let currentSpeech: string[] = [];

		for (const line of rawLines) {
			const mInline = line.match(/^(?:\[([^\]]+)\]|([A-Za-z0-9_'\s]{1,30}))\s*:\s*(.*)$/);
			if (mInline) {
				if (currentSpeech.length > 0 || currentSpeaker) {
					const text = currentSpeech.join(' ').trim();
					if (text) {
						const prefix = currentSpeaker ? `${currentSpeaker}: ` : '';
						const cue = currentCue ? `(${currentCue}) ` : '';
						turns.push(`${prefix}${cue}${text}`);
					}
					currentSpeech = [];
					currentCue = '';
				}
				currentSpeaker = (mInline[1] || mInline[2] || '').trim();
				let rest = mInline[3].trim();
				const cueM = rest.match(/^\(([^)]+)\)\s*(.*)$/);
				if (cueM) {
					currentCue = cueM[1].trim();
					rest = cueM[2].trim();
				}
				if (rest) currentSpeech.push(rest);
				continue;
			}

			const isName =
				line === line.toUpperCase() &&
				line.split(/\s+/).length <= 4 &&
				!/[.!?,;]/.test(line.slice(-1)) &&
				!line.startsWith('(');
			if (isName) {
				if (currentSpeech.length > 0 || currentSpeaker) {
					const text = currentSpeech.join(' ').trim();
					if (text) {
						const prefix = currentSpeaker ? `${currentSpeaker}: ` : '';
						const cue = currentCue ? `(${currentCue}) ` : '';
						turns.push(`${prefix}${cue}${text}`);
					}
					currentSpeech = [];
					currentCue = '';
				}
				currentSpeaker = line;
				continue;
			}

			if (line.startsWith('(') && line.endsWith(')')) {
				currentCue = line.slice(1, -1).trim();
				continue;
			}

			currentSpeech.push(line);
		}

		if (currentSpeech.length > 0 || currentSpeaker) {
			const text = currentSpeech.join(' ').trim();
			if (text) {
				const prefix = currentSpeaker ? `${currentSpeaker}: ` : '';
				const cue = currentCue ? `(${currentCue}) ` : '';
				turns.push(`${prefix}${cue}${text}`);
			}
		}

		return turns.length > 0 ? turns : rawLines;
	}

	/** Dialogue lines this clip covers: resolves 1-based indexes into structured dialogue turns. */
	const coveredLines = $derived.by(() => {
		const covered = clip.dialog_lines_covered;
		const turns = parseScreenplayTurns(scene.dialog);
		if (!turns.length) return [];
		if (!covered || covered.length === 0) return [];
		const picked = covered
			.filter((i) => Number.isInteger(i) && i >= 1 && i <= turns.length)
			.map((i) => turns[i - 1]);
		if (picked.length === 0 && turns.length === 1) {
			return turns;
		}
		return picked;
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

	async function copyImageDescription() {
		if (!body) return;
		try {
			await navigator.clipboard.writeText(body);
			copied = true;
			if (copyTimer) clearTimeout(copyTimer);
			copyTimer = setTimeout(() => (copied = false), 1500);
			toast.success('Image description copied');
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
		{#if clip.chain_from_prev}
			<span class="pill chained" title={t('shotBrief.chainFromPrev')}>🔗 {t('shotBrief.chainFromPrev')}</span>
		{/if}
		<span class="dur mono">{formatClock(clip.duration_sec || 5)}</span>
		<span class="grow"></span>
		<button
			type="button"
			class="icon-btn"
			disabled={!body}
			title={copied ? t('shotBrief.copied') : 'Copy image description'}
			aria-label="Copy image description"
			onclick={copyImageDescription}
		>
			<Icon name={copied ? 'check' : 'copy'} size={13} />
			<span class="icon-btn-text">{copied ? t('shotBrief.copied') : t('shotBrief.copy')}</span>
		</button>
		<button
			type="button"
			class="icon-btn toggle-btn"
			class:open
			aria-expanded={open}
			title={open ? t('shotBrief.collapse') : t('shotBrief.expand')}
			onclick={() => (open = !open)}
		>
			<Icon name={open ? 'chevron-up' : 'chevron-down'} size={13} />
		</button>
	</div>

	<!-- Prominent Audio Playback: always accessible before generating video -->
	{#if clip.audio_path}
		<div class="audio-playback-banner">
			<div class="audio-playback-header">
				<span class="audio-tag"><Icon name="mic" size={13} /> {t('shotBrief.dialogAudio')}</span>
				<span class="audio-hint">Preview before video generation</span>
			</div>
			<!-- svelte-ignore a11y_media_has_caption -->
			<audio controls src={assetUrl(clip.audio_path)} preload="metadata" class="audio-player"></audio>
		</div>
	{/if}

	<!-- Voice Generation Toolbar (Reference vs Default Male/Female + Regenerate) -->
	{#if projectId && (coveredLines.length > 0 || clip.audio_path)}
		<div class="voice-toolbar">
			<div class="voice-opts-row">
				<div class="voice-picker" role="radiogroup" aria-label="Voice Selection">
					<label class="voice-opt" class:active={voiceOption === 'reference'} title="Use character's recorded reference sample">
						<input type="radio" bind:group={voiceOption} value="reference" />
						<span>Reference</span>
					</label>
					<label class="voice-opt" class:active={voiceOption === 'female'} title="Default clear female voice (WomanVoice6Sec.mp3)">
						<input type="radio" bind:group={voiceOption} value="female" />
						<span>Default Female</span>
					</label>
					<label class="voice-opt" class:active={voiceOption === 'male'} title="Default warm male voice (ManVoice42Sec.mp3)">
						<input type="radio" bind:group={voiceOption} value="male" />
						<span>Default Male</span>
					</label>
				</div>
			</div>
			<div class="voice-actions-row">
				<label class="enhanced-toggle" title="Enhance prompt with Higgs expressive prosody & natural pause control tags">
					<input type="checkbox" bind:checked={enhanced} />
					<span>Higgs Expressive</span>
				</label>
				<button
					type="button"
					class="voice-gen-btn"
					class:regenerate={Boolean(clip.audio_path)}
					disabled={generatingVoice}
					onclick={generateVoice}
				>
					<Icon name={generatingVoice ? 'sparkle' : clip.audio_path ? 'refresh' : 'mic'} size={12} />
					<span>{generatingVoice ? t('shotBrief.generatingVoice') : (clip.audio_path ? 'Regenerate Voice' : t('shotBrief.generateVoice'))}</span>
				</button>
			</div>
		</div>
	{/if}

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
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 6px;
		min-height: 24px;
	}

	.label {
		font-size: 12px;
		font-weight: 700;
		color: var(--accent);
		flex-shrink: 0;
	}

	.pill {
		padding: 1px 7px;
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
		padding: 0 7px;
		font: inherit;
		font-size: 11px;
		font-weight: 600;
		color: var(--text-secondary);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
		flex-shrink: 0;
		transition: all 0.15s ease;
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

	.audio-playback-banner {
		display: flex;
		flex-direction: column;
		gap: 4px;
		background: rgba(var(--accent-rgb, 99, 102, 241), 0.06);
		border: 1px solid rgba(var(--accent-rgb, 99, 102, 241), 0.25);
		border-radius: var(--radius-sm);
		padding: 6px 8px;
	}

	.audio-playback-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.audio-tag {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: 10.5px;
		font-weight: 700;
		color: var(--accent);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.audio-hint {
		font-size: 10px;
		color: var(--text-muted);
	}

	.audio-player {
		width: 100%;
		height: 28px;
		outline: none;
	}

	.voice-toolbar {
		display: flex;
		flex-direction: column;
		gap: 6px;
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 6px 8px;
	}

	.voice-opts-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.voice-picker {
		display: flex;
		align-items: center;
		gap: 4px;
		flex-wrap: wrap;
		width: 100%;
	}

	.voice-opt {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: 10px;
		font-weight: 600;
		padding: 2px 7px;
		border-radius: var(--radius-sm);
		background: var(--bg-surface);
		border: 1px solid var(--border);
		cursor: pointer;
		color: var(--text-secondary);
		user-select: none;
		transition: all 0.15s ease;
	}

	.voice-opt.active {
		border-color: var(--accent);
		color: var(--accent);
		background: rgba(var(--accent-rgb, 99, 102, 241), 0.12);
		font-weight: 700;
	}

	.voice-opt input {
		margin: 0;
		cursor: pointer;
		display: none;
	}

	.voice-actions-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
	}

	.enhanced-toggle {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		font-size: 10.5px;
		font-weight: 600;
		color: var(--text-secondary);
		cursor: pointer;
		user-select: none;
	}

	.enhanced-toggle input {
		cursor: pointer;
		margin: 0;
		accent-color: var(--accent);
	}

	.voice-gen-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 24px;
		padding: 0 10px;
		font: inherit;
		font-size: 11px;
		font-weight: 600;
		color: #fff;
		background: var(--accent);
		border: none;
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition: opacity 0.15s;
		flex-shrink: 0;
	}

	.voice-gen-btn:hover:not(:disabled) {
		opacity: 0.9;
	}

	.voice-gen-btn.regenerate {
		background: #2563eb;
	}

	.voice-gen-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.desc {
		margin: 0;
		font-size: 12px;
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
		margin: 0;
		font-size: 11.5px;
		line-height: 1.45;
		color: var(--text-muted);
	}

	.block {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.block-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.block .k {
		display: block;
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
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

	.pill.chained {
		background: rgba(var(--accent-rgb, 99, 102, 241), 0.15);
		border-color: var(--accent);
		color: var(--accent);
	}
</style>
