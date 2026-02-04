<script lang="ts">
	import { playerStore } from '$lib/stores/player.svelte';
	import type { Track } from '$lib/api';
	import { Play, Plus, Clock, Music2 } from 'lucide-svelte';

	interface Props {
		tracks: Track[];
		showAlbum?: boolean;
		showArtist?: boolean;
		highlightId?: number | null;
	}

	let { tracks, showAlbum = true, showArtist = true, highlightId = null }: Props = $props();

	// Prevent duplicate actions (double-clicks / rapid clicks) from starting overlapping async flows.
	let isPlayInFlight = $state(false);
	let inFlightKey = $state<string | null>(null);

	// Format duration to mm:ss
	function formatDuration(seconds: number): string {
		if (!seconds || seconds < 0) return '--:--';
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	async function handlePlay(track: Track, index: number) {
		const key = `${track.id ?? 'noid'}|${track.path ?? ''}|${index}`;

		// Hard guard: if an action is in-flight, ignore further clicks (including double-click).
		// This avoids overlapping clear/add/jump sequences that can corrupt UI state.
		if (isPlayInFlight) {
			console.log('[TrackList] handlePlay ignored (in-flight):', {
				track: track.title,
				index,
				key,
				inFlightKey
			});
			return;
		}

		isPlayInFlight = true;
		inFlightKey = key;

		try {
			console.log('[TrackList] handlePlay called:', { track: track.title, index, path: track.path });

			// Album-Semantik (stabil, ohne Off-by-one/Race):
			// 1) Playlist leeren
			// 2) Alle Album-Tracks hinzufügen (in Reihenfolge)
			// 3) Zum geklickten Index springen
			// Dadurch wird nicht erst Track 1 gestartet (was häufig zu "nächster Track spielt" führt).

			console.log('[TrackList] Clearing playlist...');
			await playerStore.clearPlaylist();

			console.log('[TrackList] Adding album tracks in order:', tracks.length);
			for (const t of tracks) {
				// Sequenziell, damit die Queue-Reihenfolge garantiert stabil ist
				// (parallel kann die Reihenfolge bei manchen Backends/Netzwerken durcheinander geraten)
				await playerStore.addToPlaylist(t);
			}

			console.log('[TrackList] Jumping to index:', index, 'track:', track.title);
			await playerStore.jumpToIndex(index, track);

			// Reload playlist to show full queue
			await playerStore.loadPlaylist();
			console.log('[TrackList] handlePlay complete');
		} finally {
			// Always release the lock (even if API calls fail) to keep UI usable.
			isPlayInFlight = false;
			inFlightKey = null;
		}
	}

	function handleAdd(track: Track, event: MouseEvent) {
		event.stopPropagation();
		playerStore.addToPlaylist(track);
	}
</script>

{#if tracks.length === 0}
	<div class="flex flex-col items-center justify-center py-12 text-overlay-1">
		<Music2 size={48} class="mb-4 opacity-50" />
		<p class="text-lg">No tracks found</p>
	</div>
{:else}
	<div class="flex flex-col">
		<!-- Header -->
		<div class="grid grid-cols-[auto_1fr_auto] gap-4 px-4 py-2 text-xs text-overlay-1 uppercase tracking-wider border-b border-border">
			<span class="w-8">#</span>
			<span>Title</span>
			<span class="flex items-center gap-1">
				<Clock size={14} />
			</span>
		</div>

		<!-- Track list -->
		{#each tracks as track, index}
			<div
				class="group grid grid-cols-[auto_1fr_auto] gap-4 px-4 py-3 hover:bg-surface-0 transition-colors text-left items-center cursor-pointer
					   {track.id === highlightId ? 'bg-surface-0' : ''}"
				style={isPlayInFlight ? 'pointer-events: none; opacity: 0.7;' : undefined}
				onclick={() => handlePlay(track, index)}
				onkeydown={(e) => e.key === 'Enter' && handlePlay(track, index)}
				role="button"
				tabindex="0"
			>
				<!-- Track number / Play icon -->
				<div class="w-8 flex items-center justify-center">
					<span class="text-overlay-1 text-sm group-hover:hidden">
						{track.trackNumber || index + 1}
					</span>
					<Play
						size={16}
						class="text-accent hidden group-hover:block"
						fill="currentColor"
					/>
				</div>

				<!-- Track info -->
				<div class="min-w-0 flex flex-col gap-0.5">
					<span class="text-text truncate {track.id === highlightId ? 'text-accent' : ''}">
						{track.title}
					</span>
					<div class="flex items-center gap-1 text-sm text-overlay-1 truncate">
						{#if showArtist}
							<span class="truncate">{track.artist}</span>
						{/if}
						{#if showArtist && showAlbum}
							<span>•</span>
						{/if}
						{#if showAlbum}
							<span class="truncate">{track.album}</span>
						{/if}
					</div>
				</div>

				<!-- Duration & Actions -->
				<div class="flex items-center gap-2">
					<button
						class="p-1.5 rounded-full hover:bg-surface-1 text-overlay-1 hover:text-accent opacity-0 group-hover:opacity-100 transition-all"
						onclick={(e) => handleAdd(track, e)}
						aria-label="Add to queue"
					>
						<Plus size={16} />
					</button>
					<span class="text-sm text-overlay-1 w-12 text-right">
						{formatDuration(track.duration)}
					</span>
				</div>
			</div>
		{/each}
	</div>
{/if}
