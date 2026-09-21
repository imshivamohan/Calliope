<script lang="ts">
	/**
	 * VideoEditWorkspace — modern Edit layout for Project → Video.
	 * Hero monitor + filmstrip + meta strip + docked Omni composer.
	 * Does not reuse the old top two-card clip-stage layout.
	 */
	import { assetUrl, type Character, type Clip, type Job, type Location, type Scene, type Workflow } from '$lib/api';
	import OmniComposer from '$lib/components/OmniComposer.svelte';
	import type { AssetOption } from '$lib/assetPicker';
	import { normalizeInputRole } from '$lib/comfy/parser';
	import Icon from '$lib/components/ui/Icon.svelte';
	import ClipMonitor from './ClipMonitor.svelte';
	import ClipSourceModal from './ClipSourceModal.svelte';
	import JobInputsDrawer from './JobInputsDrawer.svelte';
	import PromptPreviewModal from './PromptPreviewModal.svelte';
	import SceneFilmstrip, { type FilmstripClip } from './SceneFilmstrip.svelte';
	import SceneScriptDrawer from './SceneScriptDrawer.svelte';
	import { t } from '$lib/i18n.svelte';
	import ShotBrief from './ShotBrief.svelte';

	type Thumb = { kind: 'image' | 'video'; src: string } | null;

	interface Progress {
		progress?: number;
		message?: string;
	}

	interface ClipSourceOption {
		/** Scene id as string, or the 'auto' / 'upload' sentinels. */
		id: string;
		label: string;
		/** Clip path — the source modal renders video thumbnails when present. */
		path?: string;
	}

	interface ClipSourceConfig {
		/** Only offered when the scene continues from the previous video and the workflow can accept it. */
		enabled: boolean;
		value: string;
		options: ClipSourceOption[];
	}

	interface Props {
		scenes: Scene[];
		/** Flattened clips in playback order — the filmstrip + selection units. */
		filmClips: FilmstripClip[];
		/** Selected clip (defaults to the scene's first when the scene has one clip). */
		selectedClip: { clip: Clip; scene: Scene; index: number; label: string } | null;
		selectedClipId: number | null;
		selected: Scene;
		locations?: Location[];
		characters?: Character[];
		status: string;
		previewPath: string | null;
		progress?: Progress | null;
		error?: string;
		errorLong?: boolean;
	/** Latest video job for the selected clip — drives the "what was sent" drawer. */
	job?: Job | null;
	/** All video jobs for the selected clip (history strip in the drawer). */
	clipJobs?: Job[];
		workflow: Workflow | undefined;
		workflows: Workflow[];
		formValues: Record<string, string | number>;
		assetOptions: AssetOption[];
		allowUpload?: boolean;
		/** Disable Generate: clip continues from the previous video but the workflow cannot accept it. */
		generateDisabled?: boolean;
		generateDisabledReason?: string;
	/** Where this continue clip's video input comes from (auto / upload / a timeline clip). */
	clipSource?: ClipSourceConfig;
	onClipSourceChange?: (value: string) => void;
	/** Upload file picked in the source modal — caller opens the file dialog. */
	onClipSourceUpload?: () => void;
	/** HITL prompt review before Generate: caller resolves + shows the modal. */
	onPreviewPrompt?: () => void;
	generateLabel?: string;
		submitting?: boolean;
		statusOfClip: (clipId: number) => string;
		thumbForClip: (clipId: number) => Thumb;
		formatClock: (sec: number) => string;
		onSelectClip: (clipId: number) => void;
		onStep: (dir: -1 | 1) => void;
	onWorkflowChange: (id: number) => void;
	onFormChange?: (values: Record<string, string | number>) => void;
	onGenerate: () => void;
	/** Render-history versioning: apply an older job's output to the clip. */
	onApplyToClip?: (job: Job, path: string) => void;
	applying?: boolean;
	projectId?: number;
	}

	let {
		projectId,
		scenes,
		filmClips,
		selectedClip,
		selectedClipId,
		selected,
		locations = [],
		characters = [],
		status,
		previewPath,
		progress = null,
		error = '',
		errorLong = false,
		job = null,
		clipJobs = [],
		workflow,
		workflows,
		formValues = $bindable(),
		assetOptions,
		allowUpload = true,
		generateDisabled = false,
		generateDisabledReason = '',
		clipSource,
		onClipSourceChange,
		onClipSourceUpload,
		onPreviewPrompt,
		generateLabel = '',
		submitting = false,
		statusOfClip,
		thumbForClip,
		formatClock,
		onSelectClip,
		onStep,
		onWorkflowChange,
		onFormChange,
		onGenerate,
		onApplyToClip,
		applying = false,
	}: Props = $props();

	let clipSourceOpen = $state(false);
	let inputsOpen = $state(false);

	const hasJobPayload = $derived(
		Boolean(
			job &&
				((typeof job.payload?.prompt === 'string' && job.payload.prompt) ||
					job.payload?.input_values),
		),
	);

	/** The label shown on the Video source trigger. */
	const clipSourceLabel = $derived.by(() => {
		if (!clipSource?.enabled) return '';
		const val = clipSource.value;
		if (val === 'auto') return t('clipSource.autoName');
		if (val === 'upload') return t('clipSource.uploadName');
		return clipSource.options.find((o) => o.id === val)?.label ?? t('clipSource.autoName');
	});

	const currentScene = $derived.by(() => {
		const baseScene = selectedClip?.scene ?? selected;
		if (!baseScene) return null;
		const fullScene = scenes.find((s) => s.id === baseScene.id);
		return fullScene ?? baseScene;
	});

	const requiredCharacters = $derived.by(() => {
		if (!currentScene) return [];
		if (currentScene.characters && currentScene.characters.length > 0) {
			return currentScene.characters;
		}
		if (currentScene.character_ids && currentScene.character_ids.length > 0 && characters.length > 0) {
			return characters.filter((c) => currentScene.character_ids.includes(c.id));
		}
		return [];
	});

	const requiredLocation = $derived.by(() => {
		if (!currentScene) return null;
		if (currentScene.location) return currentScene.location;
		if (currentScene.location_id != null && locations.length > 0) {
			return locations.find((l) => l.id === currentScene.location_id) ?? null;
		}
		return null;
	});

	function assetForCharacter(char: { id: number; name: string; portrait_path?: string | null; sheet_path?: string | null }): AssetOption | undefined {
		if (char.sheet_path) {
			const found = assetOptions.find((a) => a.path === char.sheet_path);
			if (found) return found;
		}
		if (char.portrait_path) {
			const found = assetOptions.find((a) => a.path === char.portrait_path);
			if (found) return found;
		}
		const lower = char.name.trim().toLowerCase();
		return assetOptions.find((a) => a.label.toLowerCase().includes(lower));
	}

	function assetForLocation(loc: { id: number; name: string; reference_image_path?: string | null }): AssetOption | undefined {
		if (loc.reference_image_path) {
			const found = assetOptions.find((a) => a.path === loc.reference_image_path);
			if (found) return found;
		}
		const lower = loc.name.trim().toLowerCase();
		return assetOptions.find((a) => a.label.toLowerCase().includes(lower));
	}

	function isAssetAssigned(path?: string | null): boolean {
		if (!path) return false;
		return Object.values(formValues).includes(path);
	}

	function quickAssignAsset(path: string, preferredRole: 'character' | 'location') {
		if (!workflow?.input_schema) return;
		const emptySlot =
			workflow.input_schema.find(
				(inp) =>
					(inp.kind === 'image' || inp.kind === 'image_url') &&
					!formValues[inp.nodeId] &&
					normalizeInputRole(inp.role) === preferredRole,
			) ??
			workflow.input_schema.find(
				(inp) =>
					(inp.kind === 'image' || inp.kind === 'image_url') &&
					!formValues[inp.nodeId] &&
					(!inp.role || normalizeInputRole(inp.role) === 'image'),
			);

		if (emptySlot) {
			formValues = { ...formValues, [emptySlot.nodeId]: path };
			onFormChange?.(formValues);
		}
	}
</script>

<div class="workspace">
<div class="preview-col">
		<div class="hero">
			<ClipMonitor
				{previewPath}
				{status}
				heading={(selectedClip?.clip.description || selected.heading || t('clipMonitor.untitled')).slice(0, 80)}
				orderIndex={selected.order_index}
				label={selectedClip?.label}
				idLabel={selectedClip ? t('videoEdit.clipId', { id: selectedClip.clip.id }) : selected ? t('videoEdit.sceneId', { id: selected.id }) : undefined}
				sceneId={selectedClip?.scene.id ?? selected?.id}
				{progress}
				{error}
				{errorLong}
			/>
		</div>

		<SceneFilmstrip
			clips={filmClips}
			{selectedClipId}
			{statusOfClip}
			{thumbForClip}
			{formatClock}
			{onSelectClip}
			{onStep}
		/>

		<SceneScriptDrawer scene={selected} {status} {formatClock} />
	</div>

	<aside class="dock-col" aria-label={t('videoEdit.dockAria')}>
		{#if workflow}
			{#if generateDisabled}
				<div class="continue-warning" role="alert">
					<Icon name="alert" size={16} />
					<div class="continue-warning-text">
						<span class="continue-warning-title">{t('videoEdit.noVideoInputWf')}</span>
						<span>{t('videoEdit.continueHint')}</span>
					</div>
				</div>
			{:else if clipSource?.enabled}
<div class="clip-source-row">
				<span class="clip-source-label" id="clip-source-label">{t('videoEdit.videoSource')}</span>
				<button
					type="button"
					class="clip-source-trigger"
					aria-haspopup="dialog"
					aria-expanded={clipSourceOpen}
					aria-labelledby="clip-source-label clip-source-value"
					onclick={() => (clipSourceOpen = true)}
				>
					<Icon name="film" size={14} />
					<span id="clip-source-value" class="clip-source-value">{clipSourceLabel}</span>
					<Icon name="chevron-down" size={12} />
				</button>
			</div>
			<ClipSourceModal
				bind:open={clipSourceOpen}
				value={clipSource.value}
				options={clipSource.options}
				onselect={(source) => onClipSourceChange?.(source)}
				onupload={() => onClipSourceUpload?.()}
			/>
		{/if}
		<div class="target-card" role="region" aria-label={t('videoEdit.assetHint')}>
			<div class="target-header">
				<div class="target-header-title">
					<Icon name="sparkle" size={14} />
					<span class="target-title-text">{t('videoEdit.assetHint')}</span>
				</div>
				{#if selectedClip}
					<span class="target-clip-tag">{selectedClip.label}</span>
				{/if}
			</div>

			{#if requiredCharacters.length > 0 || requiredLocation}
				<div class="target-items">
					{#each requiredCharacters as char}
						{@const opt = assetForCharacter(char)}
						{@const assetPath = opt?.path ?? char.sheet_path ?? char.portrait_path}
						{@const assigned = isAssetAssigned(assetPath)}
						<div class="target-chip char-chip" class:assigned>
							{#if assetPath}
								<img class="target-chip-thumb" src={assetUrl(assetPath)} alt={char.name} />
							{:else}
								<span class="target-chip-icon"><Icon name="assets" size={14} /></span>
							{/if}
							<div class="target-chip-info">
								<span class="target-chip-name">{char.name}</span>
								<span class="target-chip-role">{char.role || 'Character'}</span>
							</div>
							{#if assetPath}
								{#if assigned}
									<span class="target-chip-status" title={t('videoEdit.assignedAsset')}>
										<Icon name="check" size={12} />
									</span>
								{:else}
									<button
										type="button"
										class="target-chip-add"
										title={t('videoEdit.assignAsset')}
										onclick={() => quickAssignAsset(assetPath, 'character')}
									>
										<Icon name="plus" size={11} />
										<span>{t('videoEdit.assignAsset')}</span>
									</button>
								{/if}
							{/if}
						</div>
					{/each}

					{#if requiredLocation}
						{@const opt = assetForLocation(requiredLocation)}
						{@const assetPath = opt?.path ?? requiredLocation.reference_image_path}
						{@const assigned = isAssetAssigned(assetPath)}
						<div class="target-chip loc-chip" class:assigned>
							{#if assetPath}
								<img class="target-chip-thumb" src={assetUrl(assetPath)} alt={requiredLocation.name} />
							{:else}
								<span class="target-chip-icon"><Icon name="image" size={14} /></span>
							{/if}
							<div class="target-chip-info">
								<span class="target-chip-name">{requiredLocation.name}</span>
								<span class="target-chip-role">Location</span>
							</div>
							{#if assetPath}
								{#if assigned}
									<span class="target-chip-status" title={t('videoEdit.assignedAsset')}>
										<Icon name="check" size={12} />
									</span>
								{:else}
									<button
										type="button"
										class="target-chip-add"
										title={t('videoEdit.assignAsset')}
										onclick={() => quickAssignAsset(assetPath, 'location')}
									>
										<Icon name="plus" size={11} />
										<span>{t('videoEdit.assignAsset')}</span>
									</button>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{:else}
				<p class="target-empty muted">{t('videoEdit.noSceneAssets')}</p>
			{/if}

			{#if assetOptions.length === 0}
				<p class="target-hint muted">{t('videoEdit.noAssetsYet')}</p>
			{/if}
		</div>
		{#if hasJobPayload}
			<div class="job-inputs-row">
				<button
					type="button"
					class="job-inputs-trigger"
					aria-haspopup="dialog"
					aria-expanded={inputsOpen}
					onclick={() => (inputsOpen = true)}
				>
					<Icon name="info" size={14} />
					<span>{t('videoEdit.viewPrompt')}</span>
				</button>
			</div>
			<JobInputsDrawer
				bind:open={inputsOpen}
				{job}
				jobs={clipJobs}
				{workflow}
				sceneVideoPath={selectedClip?.clip.clip_path ?? selected.video_path}
				onCopySettings={(values) => {
					formValues = { ...formValues, ...values };
					onFormChange?.({ ...formValues });
				}}
				onApplyToScene={(j, path) => onApplyToClip?.(j, path)}
				applying={applying}
			/>
		{/if}
		{#if selectedClip}
			<ShotBrief
				clip={selectedClip.clip}
				scene={selectedClip.scene}
				label={selectedClip.label}
				{formatClock}
				{projectId}
				onPastePrompt={(pastedText) => {
					const promptSlot =
						workflow?.input_schema?.find(
							(inp) =>
								(inp.kind === 'text' || inp.kind === 'textarea') &&
								(inp.role === 'prompt' || inp.nodeId.toLowerCase().includes('prompt')),
						) ?? workflow?.input_schema?.find((inp) => inp.kind === 'text' || inp.kind === 'textarea');
					if (promptSlot) {
						formValues = { ...formValues, [promptSlot.nodeId]: pastedText };
						onFormChange?.(formValues);
					}
				}}
			/>
		{/if}
		<OmniComposer
			inputs={workflow.input_schema}
			bind:values={formValues}
			{workflow}
			{workflows}
			onWorkflowChange={onWorkflowChange}
			{assetOptions}
			{allowUpload}
			targetCharacters={requiredCharacters}
			targetLocation={requiredLocation?.name ?? null}
			generateLabel={generateLabel || t('videoEdit.generateLabel')}
			{submitting}
			disabled={generateDisabled}
			generateDisabledHint={generateDisabledReason}
			onChange={onFormChange}
			onSubmit={onPreviewPrompt ?? onGenerate}
		/>
		{:else}
			<div class="no-wf">
				<p class="empty-title">{t('videoEdit.noWf')}</p>
				<p class="muted">
					{t('videoEdit.enableWfPre')} <a href="/settings?tab=workflows">{t('videoEdit.wfLink')}</a>{t('videoEdit.enableWfPost')}
				</p>
			</div>
		{/if}
	</aside>
</div>

<style>
	/* Two columns: the player + strip own the left, every generation input
	   lives in the right inspector so it can't push the player out of view. */
	.workspace {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: row;
		gap: 12px;
		overflow: hidden;
	}

	.preview-col {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
		overflow: hidden;
	}

	.hero {
		flex: 1 1 auto;
		min-height: 200px;
		display: flex;
		align-items: stretch;
		justify-content: stretch;
		overflow: hidden;
		width: 100%;
	}

	/* Inspector — scrolls on its own so the player keeps the height. */
	.dock-col {
		flex: 0 0 clamp(300px, 34%, 400px);
		min-width: 280px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding-right: 2px;
	}

	.dock-col :global(.omni-shell) {
		flex-shrink: 0;
	}

	/* Very narrow: stack, player first. */
	@media (max-width: 900px) {
		.workspace {
			flex-direction: column;
			overflow-y: auto;
		}

		.preview-col {
			overflow: visible;
		}

		.dock-col {
			flex: 0 0 auto;
			overflow: visible;
		}
	}

	.continue-warning {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 10px 12px;
		margin: 0;
		border-radius: var(--radius-md);
		border: 1px solid color-mix(in srgb, var(--warning) 40%, var(--border));
		background: color-mix(in srgb, var(--warning) 10%, var(--bg-surface));
		color: var(--text-secondary);
		font-size: 13px;
	}

	.continue-warning :global(svg) {
		flex-shrink: 0;
		margin-top: 2px;
		color: var(--warning);
	}

	.continue-warning-text {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.continue-warning-title {
		font-weight: 650;
		color: var(--text-primary);
	}

	.clip-source-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
	}

	.clip-source-label {
		font-size: 12px;
		color: var(--text-secondary);
		white-space: nowrap;
	}

	.clip-source-trigger {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		max-width: 100%;
		min-width: 0;
		padding: 6px 12px;
		font: inherit;
		font-size: 13px;
		color: var(--text-primary);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
	}

	.clip-source-trigger:hover {
		border-color: var(--text-muted);
	}

	.clip-source-trigger:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.clip-source-trigger :global(svg:last-child) {
		color: var(--text-muted);
	}

	.clip-source-value {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.target-card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border-radius: var(--radius-md);
		border: 1px solid var(--border);
		background: var(--bg-surface);
	}

	.target-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.target-header-title {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-primary);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.target-header-title :global(svg) {
		color: var(--accent);
	}

	.target-clip-tag {
		font-family: var(--font-mono, monospace);
		font-size: 11px;
		font-weight: 700;
		color: var(--accent);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 1px 6px;
	}

	.target-items {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.target-chip {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 8px;
		border-radius: var(--radius-sm);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		font-size: 12px;
	}

	.target-chip.assigned {
		border-color: color-mix(in srgb, var(--success, #22c55e) 40%, var(--border));
		background: color-mix(in srgb, var(--success, #22c55e) 6%, var(--bg-elevated));
	}

	.target-chip-thumb {
		width: 28px;
		height: 28px;
		border-radius: 4px;
		object-fit: cover;
		flex-shrink: 0;
		border: 1px solid var(--border);
	}

	.target-chip-icon {
		width: 28px;
		height: 28px;
		border-radius: 4px;
		background: var(--bg-surface);
		border: 1px solid var(--border);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
		flex-shrink: 0;
	}

	.target-chip-info {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		line-height: 1.25;
	}

	.target-chip-name {
		font-weight: 600;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.target-chip-role {
		font-size: 11px;
		color: var(--text-muted);
	}

	.target-chip-status {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--success, #22c55e) 15%, transparent);
		color: var(--success, #22c55e);
		flex-shrink: 0;
	}

	.target-chip-add {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 3px 8px;
		font: inherit;
		font-size: 11px;
		font-weight: 600;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 10%, var(--bg-surface));
		border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
		border-radius: var(--radius-sm);
		cursor: pointer;
		flex-shrink: 0;
		transition: background 150ms ease, border-color 150ms ease;
	}

	.target-chip-add:hover {
		background: color-mix(in srgb, var(--accent) 20%, var(--bg-surface));
		border-color: var(--accent);
	}

	.target-empty,
	.target-hint {
		margin: 0;
		font-size: 12px;
		line-height: 1.4;
	}

	.job-inputs-row {
		display: flex;
		justify-content: flex-end;
		margin: 0;
	}

	.job-inputs-trigger {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		font: inherit;
		font-size: 12px;
		font-weight: 500;
		color: var(--text-secondary);
		background: transparent;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition:
			color 150ms ease,
			border-color 150ms ease;
	}

	.job-inputs-trigger:hover {
		color: var(--text-primary);
		border-color: var(--text-muted);
	}

	.job-inputs-trigger:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.no-wf {
		padding: 20px;
		text-align: center;
		border: 1px dashed var(--border);
		border-radius: var(--radius-lg);
		background: var(--bg-surface);
	}

	.empty-title {
		margin: 0 0 4px;
		font-size: 14px;
		font-weight: 600;
		color: var(--text-primary);
	}

	.muted {
		margin: 0;
		font-size: 13px;
		color: var(--text-secondary);
	}

	.muted a {
		color: var(--accent);
	}
</style>
