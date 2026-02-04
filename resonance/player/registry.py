"""
Player Registry - Central repository for connected players.

The registry tracks all connected Squeezebox players and provides
methods to look them up by various identifiers.
"""

import asyncio
import logging
from typing import Iterator

from resonance.player.client import PlayerClient

logger = logging.getLogger(__name__)


class PlayerRegistry:
    """
    Central registry for all connected Squeezebox players.

    Players are indexed by their MAC address (the primary identifier
    used by the Slimproto protocol) and can also be looked up by
    their IP address or player name.

    Thread-safety: This class uses an asyncio lock for safe concurrent
    access from multiple coroutines.
    """

    def __init__(self) -> None:
        """Initialize an empty player registry."""
        self._players_by_mac: dict[str, PlayerClient] = {}
        self._lock = asyncio.Lock()

    async def register(self, player: PlayerClient) -> None:
        """
        Register a new player in the registry.

        If a player with the same MAC address already exists, it will
        be replaced (this handles reconnection scenarios).

        Args:
            player: The player client to register.
        """
        async with self._lock:
            mac = player.mac_address

            if mac in self._players_by_mac:
                old_player = self._players_by_mac[mac]
                logger.info(
                    "Player reconnected: %s (replacing old connection)",
                    mac,
                )
                # Close old connection gracefully
                await old_player.disconnect()

            self._players_by_mac[mac] = player
            logger.info(
                "Player registered: %s (%s)",
                mac,
                player.name or "unnamed",
            )

    async def unregister(self, mac_address: str) -> PlayerClient | None:
        """
        Remove a player from the registry.

        Args:
            mac_address: The MAC address of the player to remove.

        Returns:
            The removed player, or None if not found.
        """
        async with self._lock:
            player = self._players_by_mac.pop(mac_address, None)
            if player:
                logger.info("Player unregistered: %s", mac_address)
            return player

    async def get_by_mac(self, mac_address: str) -> PlayerClient | None:
        """
        Look up a player by its MAC address.

        Args:
            mac_address: The MAC address to look up.

        Returns:
            The player client, or None if not found.
        """
        async with self._lock:
            return self._players_by_mac.get(mac_address)

    async def get_by_ip(self, ip_address: str) -> PlayerClient | None:
        """
        Look up a player by its IP address.

        Note: Multiple players could potentially have the same IP
        (e.g., behind NAT), so this returns the first match.

        Args:
            ip_address: The IP address to look up.

        Returns:
            The first matching player, or None if not found.
        """
        async with self._lock:
            for player in self._players_by_mac.values():
                if player.ip_address == ip_address:
                    return player
            return None

    async def get_by_name(self, name: str) -> PlayerClient | None:
        """
        Look up a player by its display name.

        Args:
            name: The player name to look up (case-insensitive).

        Returns:
            The first matching player, or None if not found.
        """
        name_lower = name.lower()
        async with self._lock:
            for player in self._players_by_mac.values():
                if player.name and player.name.lower() == name_lower:
                    return player
            return None

    async def get_all(self) -> list[PlayerClient]:
        """
        Get a list of all connected players.

        Returns:
            A list of all registered players (copy, safe to iterate).
        """
        async with self._lock:
            return list(self._players_by_mac.values())

    async def disconnect_all(self) -> None:
        """
        Disconnect all players and clear the registry.

        This is typically called during server shutdown.
        """
        async with self._lock:
            players = list(self._players_by_mac.values())
            self._players_by_mac.clear()

        # Disconnect outside the lock to avoid holding it during I/O
        for player in players:
            try:
                await player.disconnect()
            except Exception as e:
                logger.warning(
                    "Error disconnecting player %s: %s",
                    player.mac_address,
                    e,
                )

        logger.info("All players disconnected (%d total)", len(players))

    def __len__(self) -> int:
        """Return the number of connected players."""
        return len(self._players_by_mac)

    def __contains__(self, mac_address: str) -> bool:
        """Check if a player with the given MAC address is registered."""
        return mac_address in self._players_by_mac

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered MAC addresses."""
        return iter(self._players_by_mac)

    def __bool__(self) -> bool:
        """A registry instance is always truthy, even when empty."""
        return True
