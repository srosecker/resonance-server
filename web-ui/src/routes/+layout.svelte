<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { playerStore } from '$lib/stores/player.svelte';

	let { children } = $props();

	onMount(() => {
		playerStore.initialize();

		return () => {
			playerStore.stopPolling();
		};
	});
</script>

<div class="min-h-screen bg-crust flex flex-col">
	{@render children()}
</div>
