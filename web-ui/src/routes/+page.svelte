<script lang="ts">
	import { playerStore } from '$lib/stores/player.svelte';
	import { colorStore } from '$lib/stores/color.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { api, type Track, type Artist, type Album } from '$lib/api';
	import NowPlaying from '$lib/components/NowPlaying.svelte';
	import PlayerSelector from '$lib/components/PlayerSelector.svelte';
	import TrackList from '$lib/components/TrackList.svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import Queue from '$lib/components/Queue.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import AddFolderModal from '$lib/components/AddFolderModal.svelte';
	import {
		Library,
		Users,
		Disc3,
		ChevronRight,
		ArrowLeft,
		RefreshCw,
		FolderPlus,
		Menu,
		Wifi,
		WifiOff,
		Trash2
	} from 'lucide-svelte';

	// Data
	let artists = $state<Artist[]>([]);
	let albums = $state<Album[]>([]);
	let tracks = $state<Track[]>([]);
	let searchResults = $state<Track[]>([]);
	let isLoadingLibrary = $state(false);

	// Delete confirmation state
	let albumToDelete = $state<Album | null>(null);
	let isDeleting = $state(false);

	// Modal handling via store proxy
	let showAddFolderModal = $derived(uiStore.activeModal === 'add-folder');
	let showDeleteConfirm = $derived(albumToDelete !== null);

	// Breadcrumb navigation
	const breadcrumbs = $derived(() => {
		const crumbs: Array<{ label: string; action: () => void }> = [
			{ label: 'Library', action: () => uiStore.navigateTo('artists') }
		];

		if (uiStore.selectedArtist) {
			crumbs.push({
				label: uiStore.selectedArtist.name,
				action: () => {
					uiStore.selectedAlbum = null;
					uiStore.currentView = 'albums';
				}
			});
		}

		if (uiStore.selectedAlbum) {
			crumbs.push({
				label: uiStore.selectedAlbum.name,
				action: () => {}
			});
		}

		return crumbs;
	});

	// Data loading
	async function loadArtists() {
		isLoadingLibrary = true;
		try {
			const result = await api.getArtists(0, 100);
			artists = result.artists;
		} catch (error) {
			console.error('Failed to load artists:', error);
		} finally {
			isLoadingLibrary = false;
		}
	}

	async function loadAlbums(artistId?: string) {
		isLoadingLibrary = true;
		try {
			const result = await api.getAlbums(0, 100, artistId);
			albums = result.albums;
		} catch (error) {
			console.error('Failed to load albums:', error);
		} finally {
			isLoadingLibrary = false;
		}
	}

	async function loadTracks() {
		if (!uiStore.selectedAlbum) return;
		isLoadingLibrary = true;
		try {
			const result = await api.getTracks(0, 100, uiStore.selectedAlbum.id);
			tracks = result.tracks;
		} catch (error) {
			console.error('Failed to load tracks:', error);
		} finally {
			isLoadingLibrary = false;
		}
	}

	async function handleSearch(query: string) {
		uiStore.navigateTo('search');
		isLoadingLibrary = true;
		try {
			const result = await api.search(query);
			searchResults = result.tracks;
		} catch (error) {
			console.error('Failed to search:', error);
		} finally {
			isLoadingLibrary = false;
		}
	}

	function handleClearSearch() {
		searchResults = [];
		if (uiStore.currentView === 'search') {
			uiStore.navigateTo('artists');
		}
	}

	async function handleRescan() {
		try {
			await api.rescan();
			// Reload current view
			if (uiStore.currentView === 'artists') {
				loadArtists();
			}
		} catch (error) {
			console.error('Failed to start rescan:', error);
		}
	}

	function handleOpenAddFolder() {
		uiStore.openModal('add-folder');
	}

	function handleCloseAddFolder() {
		uiStore.closeModal();
		// Reload artists after closing modal (in case scan finished)
		if (uiStore.currentView === 'artists') {
			loadArtists();
		}
	}

	// Album deletion handlers
	function handleDeleteAlbumClick(album: Album, event: MouseEvent) {
		event.stopPropagation();
		albumToDelete = album;
	}

	function handleCancelDelete() {
		albumToDelete = null;
	}

	async function handleConfirmDelete() {
		if (!albumToDelete) return;

		isDeleting = true;
		try {
			const result = await api.deleteAlbum(albumToDelete.id);
			console.log('Album deleted:', result);

			// Reload albums list
			await loadAlbums(uiStore.selectedArtist?.id);

			// If no albums left, go back to artists
			if (albums.length === 0) {
				uiStore.navigateTo('artists');
				await loadArtists();
			}
		} catch (error) {
			console.error('Failed to delete album:', error);
			alert('Failed to delete album: ' + (error as Error).message);
		} finally {
			isDeleting = false;
			albumToDelete = null;
		}
	}

	// Reactive Data Loading
	// When store state changes, load the appropriate data
	$effect(() => {
		const view = uiStore.currentView;
		if (view === 'artists') {
			loadArtists();
		} else if (view === 'albums') {
			// Load all albums or filtered by artist
			loadAlbums(uiStore.selectedArtist?.id);
		} else if (view === 'tracks' && uiStore.selectedAlbum) {
			loadTracks();
		}
	});

	// Initial load & setup
	// NOTE: playerStore.initialize() is called in +layout.svelte to avoid duplicate polling.
	$effect(() => {
		colorStore.initialize();
	});
</script>

<div class="flex h-screen overflow-hidden">
	<!-- Left Sidebar Navigation -->
	<Sidebar />

	<!-- Main Content Area -->
	<div class="flex-1 flex flex-col min-w-0 bg-base">
		<!-- Header -->
		<header class="glass border-b border-border px-6 py-4">
			<div class="flex items-center justify-between gap-4">
				<!-- Sidebar Toggle (Mobile/Tablet) & Status -->
				<div class="flex items-center gap-3">
					<button
						class="lg:hidden p-2 -ml-2 rounded-lg hover:bg-surface-0 text-overlay-1 hover:text-text transition-colors"
						onclick={() => uiStore.toggleSidebar()}
					>
						<Menu size={24} />
					</button>

					<div class="flex items-center gap-2 text-xs text-overlay-1">
						{#if playerStore.isConnected}
							<Wifi size={14} class="text-success" />
							<span class="hidden sm:inline">Connected</span>
						{:else}
							<WifiOff size={14} class="text-error" />
							<span class="hidden sm:inline">Disconnected</span>
						{/if}
					</div>
				</div>

				<!-- Search -->
				<div class="flex-1 max-w-xl">
					<SearchBar
						onSearch={handleSearch}
						onClear={handleClearSearch}
					/>
				</div>

				<!-- Player Selector -->
				<div class="w-48 sm:w-64">
					<PlayerSelector />
				</div>
			</div>
		</header>

		<!-- Content -->
		<div class="flex-1 flex overflow-hidden">
			<!-- Library Browser -->
			<main class="flex-1 flex flex-col min-w-0 overflow-hidden relative">
				<!-- Library Header (Breadcrumbs & Actions) -->
				{#if uiStore.currentView !== 'settings' && uiStore.currentView !== 'playlists'}
					<div class="flex items-center justify-between px-6 py-4 border-b border-border bg-base/50 backdrop-blur-sm z-10">
						<div class="flex items-center gap-4 overflow-hidden">
							{#if uiStore.selectedArtist || uiStore.selectedAlbum}
								<button
									class="p-2 rounded-lg hover:bg-surface-0 text-overlay-1 hover:text-text transition-colors shrink-0"
									onclick={() => uiStore.goBack()}
									aria-label="Go back"
								>
									<ArrowLeft size={20} />
								</button>
							{/if}

							<!-- Breadcrumbs -->
							<nav class="flex items-center gap-1 text-sm overflow-hidden whitespace-nowrap mask-linear-fade">
								{#each breadcrumbs() as crumb, index}
									{#if index > 0}
										<ChevronRight size={16} class="text-overlay-0 shrink-0" />
									{/if}
									<button
										class="px-2 py-1 rounded hover:bg-surface-0 transition-colors truncate max-w-[200px]
											{index === breadcrumbs().length - 1 ? 'text-text font-medium' : 'text-overlay-1'}"
										onclick={crumb.action}
									>
										{crumb.label}
									</button>
								{/each}
							</nav>
						</div>

						<div class="flex items-center gap-2 shrink-0">
							<button
								class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-0 text-overlay-1 hover:text-text transition-colors"
								onclick={handleOpenAddFolder}
								aria-label="Add music folder"
							>
								<FolderPlus size={18} />
								<span class="text-sm hidden sm:inline">Add Folder</span>
							</button>
							<button
								class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-0 text-overlay-1 hover:text-text transition-colors"
								onclick={handleRescan}
								aria-label="Rescan library"
							>
								<RefreshCw size={18} class={isLoadingLibrary ? 'animate-spin' : ''} />
								<span class="text-sm hidden sm:inline">Rescan</span>
							</button>
						</div>
					</div>
				{/if}

				<!-- Library Content -->
				<div class="flex-1 overflow-y-auto">
					{#if uiStore.currentView === 'artists'}
						<!-- Artists Grid -->
						<div class="p-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
							{#each artists as artist}
								<button
									class="group flex flex-col items-center gap-3 p-4 rounded-xl hover:bg-surface-0 transition-colors"
									onclick={() => uiStore.viewArtist(artist)}
								>
									<div class="w-24 h-24 sm:w-32 sm:h-32 rounded-full bg-surface-1 flex items-center justify-center group-hover:bg-surface-2 transition-colors relative overflow-hidden">
										<Users size={48} class="text-overlay-0 group-hover:text-accent transition-colors relative z-10" />
										<div class="absolute inset-0 bg-gradient-to-tr from-surface-1 to-surface-0 opacity-0 group-hover:opacity-100 transition-opacity"></div>
									</div>
									<div class="text-center min-w-0 w-full">
										<p class="text-text font-medium truncate">{artist.name}</p>
										<p class="text-sm text-overlay-1">{artist.albumCount} albums</p>
									</div>
								</button>
							{/each}
						</div>

						{#if artists.length === 0 && !isLoadingLibrary}
							<div class="flex flex-col items-center justify-center h-full text-overlay-1 p-8">
								<div class="w-20 h-20 rounded-full bg-surface-0 flex items-center justify-center mb-6">
									<Library size={40} class="opacity-50" />
								</div>
								<h3 class="text-xl font-medium text-text mb-2">Your library is empty</h3>
								<p class="text-sm mb-6 text-center max-w-sm">Add a music folder to start scanning your collection. Supports local folders with FLAC, MP3, and more.</p>
								<button
									class="px-4 py-2 bg-accent text-mantle font-medium rounded-lg hover:bg-accent-hover transition-colors"
									onclick={handleOpenAddFolder}
								>
									Add Music Folder
								</button>
							</div>
						{/if}

					{:else if uiStore.currentView === 'albums'}
						<!-- Albums Grid -->
						<div class="p-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
							{#each albums as album}
								<div class="group relative">
									<button
										class="flex flex-col gap-3 p-3 -m-3 rounded-xl hover:bg-surface-0 transition-colors text-left w-full"
										onclick={() => uiStore.viewAlbum(album)}
									>
										<div class="aspect-square rounded-lg bg-surface-1 flex items-center justify-center group-hover:bg-surface-2 transition-colors overflow-hidden shadow-lg group-hover:shadow-xl group-hover:scale-102 duration-300 relative">
											{#if album.coverArt}
												<img src={album.coverArt} alt={album.name} class="w-full h-full object-cover" />
												<div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
											{:else}
												<Disc3 size={48} class="text-overlay-0 group-hover:text-accent transition-colors" />
											{/if}
										</div>
										<div class="min-w-0 px-1">
											<p class="text-text font-medium truncate">{album.name}</p>
											<p class="text-sm text-overlay-1 truncate">{album.artist}</p>
											{#if album.year}
												<p class="text-xs text-overlay-0 mt-0.5">{album.year}</p>
											{/if}
										</div>
									</button>
									<!-- Delete button (shown on hover) -->
									<button
										class="absolute top-1 right-1 p-1.5 rounded-full bg-error/80 text-white opacity-0 group-hover:opacity-100 hover:bg-error transition-all shadow-lg"
										onclick={(e) => handleDeleteAlbumClick(album, e)}
										aria-label="Delete album"
										title="Delete album from library"
									>
										<Trash2 size={14} />
									</button>
								</div>
							{/each}
						</div>

					{:else if uiStore.currentView === 'tracks'}
						<!-- Track List -->
						<TrackList
							{tracks}
							showAlbum={false}
							highlightId={playerStore.currentTrack?.id}
						/>

					{:else if uiStore.currentView === 'search'}
						<!-- Search Results -->
						<div class="p-6">
							<h2 class="text-lg font-semibold text-text mb-4">Search Results</h2>
							{#if searchResults.length > 0}
								<TrackList
									tracks={searchResults}
									highlightId={playerStore.currentTrack?.id}
								/>
							{:else if !isLoadingLibrary}
								<div class="text-overlay-1 text-center py-12">
									<p>No results found</p>
								</div>
							{/if}
						</div>

					{:else if uiStore.currentView === 'playlists'}
						<div class="flex flex-col items-center justify-center h-full text-overlay-1">
							<div class="w-16 h-16 rounded-full bg-surface-0 flex items-center justify-center mb-4">
								<Users size={32} class="opacity-50" />
							</div>
							<p>Playlists coming soon</p>
						</div>

					{:else if uiStore.currentView === 'settings'}
						<div class="flex flex-col items-center justify-center h-full text-overlay-1">
							<div class="w-16 h-16 rounded-full bg-surface-0 flex items-center justify-center mb-4">
								<Users size={32} class="opacity-50" />
							</div>
							<p>Settings coming soon</p>
						</div>
					{/if}

					{#if isLoadingLibrary}
						<div class="flex items-center justify-center py-12">
							<RefreshCw size={32} class="dynamic-accent color-transition animate-spin" />
						</div>
					{/if}
				</div>

				<!-- Now Playing Bar (Bottom) -->
				<div class="border-t border-border p-4 bg-mantle/50 backdrop-blur-md z-20">
					<NowPlaying />
				</div>
			</main>

			<!-- Queue Sidebar -->
			<aside class="w-80 border-l border-border bg-mantle hidden 2xl:flex flex-col shrink-0">
				<Queue />
			</aside>
		</div>
	</div>
</div>

<!-- Add Folder Modal -->
{#if showAddFolderModal}
	<AddFolderModal isOpen={true} onClose={handleCloseAddFolder} />
{/if}

<!-- Delete Album Confirmation Modal -->
{#if showDeleteConfirm && albumToDelete}
	<div class="fixed inset-0 z-50 flex items-center justify-center">
		<!-- Backdrop -->
		<button
			class="absolute inset-0 bg-black/60 backdrop-blur-sm"
			onclick={handleCancelDelete}
			aria-label="Cancel"
		></button>

		<!-- Modal -->
		<div class="relative bg-mantle border border-border rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
			<h2 class="text-xl font-semibold text-text mb-2">Delete Album?</h2>
			<p class="text-overlay-1 mb-4">
				Are you sure you want to delete <strong class="text-text">"{albumToDelete.name}"</strong> by {albumToDelete.artist}?
			</p>
			<p class="text-sm text-overlay-0 mb-6">
				This will permanently remove all tracks from this album from your library.
				The files on disk will not be deleted.
			</p>

			<div class="flex gap-3 justify-end">
				<button
					class="px-4 py-2 rounded-lg hover:bg-surface-0 text-overlay-1 hover:text-text transition-colors"
					onclick={handleCancelDelete}
					disabled={isDeleting}
				>
					Cancel
				</button>
				<button
					class="px-4 py-2 rounded-lg bg-error text-white hover:bg-error/80 transition-colors flex items-center gap-2"
					onclick={handleConfirmDelete}
					disabled={isDeleting}
				>
					{#if isDeleting}
						<RefreshCw size={16} class="animate-spin" />
						Deleting...
					{:else}
						<Trash2 size={16} />
						Delete Album
					{/if}
				</button>
			</div>
		</div>
	</div>
{/if}
