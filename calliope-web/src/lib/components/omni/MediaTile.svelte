<script lang="ts">
	/**
	 * MediaTile — square thumbnail for image/ref/audio inputs.
	 * Clicking opens a tabbed asset picker modal (characters / environments /
	 * items / uploads) instead of a clipped dropdown.
	 */
	import { assetUrl } from '$lib/api';
	import type { AssetOption } from '$lib/assetPicker';
	import type { ComfyDynamicInput } from '$lib/comfy/types';
	import AssetPickerModal from './AssetPickerModal.svelte';
	import Icon from '$lib/components/ui/Icon.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import { acceptForKind } from '$lib/comfy/useUpload.svelte';
	import { toast } from '$lib/toast';
	import { t } from '$lib/i18n.svelte';

	interface Props {
		input: ComfyDynamicInput;
		value: string;
		uploadingName: string | null;
		assetOptions?: AssetOption[];
		allowUpload?: boolean;
		invalid?: boolean;
		targetAssetName?: string | null;
		onselectFile: (file: File) => void;
		onselectAsset: (path: string) => void;
		onclear: () => void;
	}

	let {
		input,
		value,
		uploadingName,
		assetOptions = [],
		allowUpload = true,
		invalid = false,
		targetAssetName = null,
		onselectFile,
		onselectAsset,
		onclear,
	}: Props = $props();

	let fileInput = $state<HTMLInputElement | null>(null);
	let dragOver = $state(false);
	let pickerOpen = $state(false);

	function openPicker() {
		if (uploadingName) return;
		if (matchingAssets.length || allowUpload) {
			pickerOpen = true;
			return;
		}
		fileInput?.click();
	}

	function onFileChosen(e: Event) {
		const el = e.currentTarget as HTMLInputElement;
		const file = el.files?.[0];
		el.value = '';
		if (file) onselectFile(file);
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (uploadingName) return;
		const file = e.dataTransfer?.files?.[0];
		if (file) onselectFile(file);
	}

	function hideBrokenThumb(e: Event) {
		const img = e.currentTarget as HTMLImageElement | null;
		if (img) img.style.display = 'none';
	}

	const thumbSrc = $derived(value ? assetUrl(value) : null);

	const isImageKind = $derived(input.kind === 'image' || input.kind === 'image_url');
	const isVideoKind = $derived(input.kind === 'video');
	const matchingAssets = $derived.by(() => {
		// The same path can arrive twice (e.g. a scene clip that was also
		// uploaded to the playground). Duplicate keys crash the keyed each
		// in the picker grid, so dedupe by path first.
		const seen = new Set<string>();
		return assetOptions.filter((o) => {
			const match =
				!o.kind || o.kind === input.kind || (isImageKind && o.kind === 'image');
			if (!match || seen.has(o.path)) return false;
			seen.add(o.path);
			return true;
		});
	});

	const displayLabel = $derived(
		input.role === 'character'
			? t('omni.roleCharacter')
			: input.role === 'location'
				? t('omni.roleLocation')
				: input.role === 'video'
					? t('omni.roleVideo')
					: input.role === 'audio'
						? t('omni.roleAudio')
						: input.label,
	);

	const accept = $derived(acceptForKind(input.kind));

	let tilePasted = $state(false);
	let tilePasteTimer: ReturnType<typeof setTimeout> | null = null;

	async function pasteReferenceFromClipboard(e: MouseEvent) {
		e.stopPropagation();
		try {
			if (navigator.clipboard.read) {
				try {
					const items = await navigator.clipboard.read();
					for (const item of items) {
						const imageType = item.types.find((t) => t.startsWith('image/'));
						if (imageType) {
							const blob = await item.getType(imageType);
							const ext = imageType.split('/')[1] || 'png';
							const file = new File([blob], `pasted_ref_${Date.now()}.${ext}`, { type: imageType });
							onselectFile(file);
							tilePasted = true;
							if (tilePasteTimer) clearTimeout(tilePasteTimer);
							tilePasteTimer = setTimeout(() => (tilePasted = false), 1500);
							toast.success('Pasted image from clipboard');
							return;
						}
					}
				} catch {
					// Fall through to text
				}
			}

			const text = (await navigator.clipboard.readText()).trim();
			if (!text) {
				toast.error('Clipboard is empty');
				return;
			}
			const lower = text.toLowerCase();
			const isAudioFile = /\.(mp3|wav|ogg|flac|m4a|aac|wma)(\?.*)?$/i.test(lower);
			const isVideoFile = /\.(mp4|webm|mov|mkv|avi)(\?.*)?$/i.test(lower);
			const isImageFile = /\.(png|jpg|jpeg|webp|gif|bmp|tiff)(\?.*)?$/i.test(lower) || text.startsWith('data:image/');

			const matched = assetOptions.find(
				(a) => a.path === text || a.label.toLowerCase() === text.toLowerCase() || a.path.includes(text),
			);

			if (isImageKind) {
				if (isAudioFile || matched?.kind === 'audio') {
					toast.error('This input requires an image reference, not audio.');
					return;
				}
				if (isVideoFile || matched?.kind === 'video') {
					toast.error('This input requires an image reference, not video.');
					return;
				}
				if (!matched && !isImageFile) {
					toast.error('Clipboard does not contain a valid image path or URL.');
					return;
				}
			} else if (isVideoKind) {
				if (isAudioFile || matched?.kind === 'audio') {
					toast.error('This input requires a video reference, not audio.');
					return;
				}
			}

			if (matched) {
				onselectAsset(matched.path);
			} else {
				onselectAsset(text);
			}
			tilePasted = true;
			if (tilePasteTimer) clearTimeout(tilePasteTimer);
			tilePasteTimer = setTimeout(() => (tilePasted = false), 1500);
			toast.success('Pasted reference from clipboard');
		} catch {
			toast.error('Could not access clipboard');
		}
	}
</script>

<div class="tile-wrap">
	<input
		bind:this={fileInput}
		type="file"
		class="sr-only"
		accept={accept || acceptForKind(input.kind)}
		onchange={onFileChosen}
	/>

	<div
		class="tile"
		class:filled={!!value}
		class:dragover={dragOver}
		class:invalid
		ondragenter={(e) => {
			e.preventDefault();
			dragOver = true;
		}}
		ondragleave={() => (dragOver = false)}
		ondragover={(e) => e.preventDefault()}
		ondrop={onDrop}
		onclick={openPicker}
		onkeydown={(e) => {
			if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				openPicker();
			}
		}}
		role="button"
		tabindex="0"
		title={displayLabel}
		aria-haspopup="dialog"
		aria-expanded={pickerOpen}
	>
		{#if uploadingName}
			<div class="tile-uploading">
				<Spinner size="sm" />
			</div>
		{:else if value && thumbSrc && isImageKind}
			<img class="tile-thumb" src={thumbSrc} alt={displayLabel} onerror={hideBrokenThumb} />
		{:else if value && isVideoKind && thumbSrc}
			<!-- svelte-ignore a11y_media_has_caption -->
			<video class="tile-thumb" src={thumbSrc} muted playsinline></video>
		{:else if value}
			<div class="tile-file">
				<Icon name={input.kind === 'audio' ? 'music' : isVideoKind ? 'film' : 'image'} size={20} />
			</div>
		{:else}
			<div class="tile-empty">
				<Icon name="plus" size={20} />
			</div>
		{/if}

		{#if !uploadingName}
			<button
				type="button"
				class="tile-paste"
				title="Paste image or reference from clipboard"
				onclick={pasteReferenceFromClipboard}
				aria-label="Paste reference from clipboard"
			>
				<Icon name={tilePasted ? 'check' : 'clipboard'} size={11} />
			</button>
		{/if}

		{#if value && !uploadingName}
			<button
				type="button"
				class="tile-remove"
				onclick={(e) => {
					e.stopPropagation();
					onclear();
				}}
				aria-label={t('omni.removeSlot', { label: displayLabel })}
			>
				<Icon name="close" size={12} />
			</button>
		{/if}
	</div>

	<span class="tile-label">{displayLabel}</span>
	{#if targetAssetName && !value}
		<span class="tile-target" title={targetAssetName}>{targetAssetName}</span>
	{/if}

	{#if invalid && !value}
		<span class="tile-req">{t('omni.required')}</span>
	{/if}
</div>

<AssetPickerModal
	bind:open={pickerOpen}
	title={t('omni.choose', { label: displayLabel })}
	suggestedName={targetAssetName}
	assets={matchingAssets}
	{value}
	kind={input.kind}
	{allowUpload}
	onselect={onselectAsset}
	onupload={() => fileInput?.click()}
	onclear={value ? onclear : undefined}
/>

<style>
	.tile-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		position: relative;
	}

	.tile {
		position: relative;
		width: 64px;
		height: 64px;
		border-radius: var(--radius-md);
		border: 1.5px dashed var(--border);
		background: var(--bg-elevated);
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		overflow: hidden;
		transition:
			border-color 0.15s,
			background 0.15s;
	}

	.tile:hover:not(.filled) {
		border-color: var(--text-muted);
	}

	.tile:focus-visible {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 3px var(--accent-glow);
	}

	.tile.dragover {
		border-color: var(--accent);
		background: var(--accent-glow);
		border-style: solid;
	}

	.tile.filled {
		border: 1px solid var(--border);
	}

	.tile.invalid {
		border-color: var(--error);
	}

	.tile-empty {
		color: var(--text-muted);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.tile-thumb {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.tile-file {
		color: var(--text-muted);
	}

	.tile-uploading {
		color: var(--text-muted);
	}

	.tile-remove {
		position: absolute;
		top: 4px;
		right: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 9999px;
		background: rgba(0, 0, 0, 0.65);
		border: none;
		color: white;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s;
		z-index: 2;
	}

	.tile:hover .tile-remove {
		opacity: 1;
	}

	.tile-remove:hover {
		background: var(--error);
	}

	.tile-paste {
		position: absolute;
		top: 4px;
		left: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 9999px;
		background: rgba(0, 0, 0, 0.65);
		border: none;
		color: white;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s, background 0.15s;
		z-index: 2;
	}

	.tile:hover .tile-paste,
	.tile:not(.filled) .tile-paste {
		opacity: 0.85;
	}

	.tile-paste:hover {
		opacity: 1 !important;
		background: var(--accent);
		color: white;
	}

	.tile-label {
		font-size: 10px;
		color: var(--text-muted);
		font-weight: 500;
		max-width: 72px;
		text-align: center;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tile-target {
		font-size: 9px;
		color: var(--accent);
		font-weight: 600;
		max-width: 76px;
		text-align: center;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		background: rgba(99, 102, 241, 0.12);
		padding: 1px 4px;
		border-radius: var(--radius-xs, 2px);
		border: 1px solid rgba(99, 102, 241, 0.25);
	}

	.tile-req {
		font-size: 9px;
		color: var(--error);
		font-weight: 600;
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		border: 0;
	}
</style>
