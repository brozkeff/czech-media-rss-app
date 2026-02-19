"""Tkinter desktop UI for browsing Czech and Slovak RSS headlines."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from threading import Event
from tkinter import ttk
from typing import Callable

from .config import MEDIA_SOURCES, PRESET_DEFINITIONS
from .feeds import NewsItem, SourceNewsResult, get_latest_news


class CzechMediaRssApp:
    """Main application window for feed source selection and headline browsing."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize UI state and render widgets.

        Args:
            root: Root Tk window.
        """
        self.root = root
        self.root.title("Czech & Slovak Media RSS")
        self.root.geometry("1120x680")
        self.root.minsize(980, 600)

        self.is_closing = False
        self.fetch_in_progress = False
        self.cancel_event: Event | None = None

        self.media_sources = list(MEDIA_SOURCES)
        self.filtered_indices = list(range(len(self.media_sources)))
        self.link_map: dict[str, str] = {}

        self.search_var = tk.StringVar()
        self.country_var = tk.StringVar(value="ALL")
        self.status_var = tk.StringVar(value="Select sources and fetch the latest news.")
        self.progress_var = tk.StringVar(value="Idle")
        self.last_fetch_var = tk.StringVar(value="Last fetch: never")

        self.preset_label_to_id = {
            item["label"]: preset_id for preset_id, item in PRESET_DEFINITIONS.items()
        }
        self.preset_var = tk.StringVar(value=self._default_preset_label())

        self._build_ui()
        self._refresh_source_list()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _default_preset_label(self) -> str:
        """Return a stable default preset label for the combobox."""
        if not self.preset_label_to_id:
            return ""
        return next(iter(self.preset_label_to_id.keys()))

    def _build_ui(self) -> None:
        """Build primary two-pane application layout."""
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        paned = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 12, 0))
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        self._build_source_pane(left)
        self._build_results_pane(right)

    def _build_source_pane(self, parent: ttk.Frame) -> None:
        """Build source search, filters, and selection controls."""
        ttk.Label(parent, text="Search source:").pack(anchor=tk.W)
        self.search_entry = ttk.Entry(parent, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X, pady=(4, 8))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._refresh_source_list())

        country_frame = ttk.LabelFrame(parent, text="Country")
        country_frame.pack(fill=tk.X, pady=(0, 8))
        for country in ("ALL", "CZ", "SK"):
            ttk.Radiobutton(
                country_frame,
                text=country,
                value=country,
                variable=self.country_var,
                command=self._refresh_source_list,
            ).pack(side=tk.LEFT, padx=(4, 8), pady=4)

        preset_frame = ttk.LabelFrame(parent, text="Preset")
        preset_frame.pack(fill=tk.X, pady=(0, 8))
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(self.preset_label_to_id.keys()),
            state="readonly",
        )
        self.preset_combo.pack(fill=tk.X, padx=6, pady=(6, 4))
        self.apply_preset_button = ttk.Button(
            preset_frame,
            text="Apply preset",
            command=self._apply_preset,
        )
        self.apply_preset_button.pack(fill=tk.X, padx=6, pady=(0, 6))

        list_frame = ttk.LabelFrame(parent, text="Available sources")
        list_frame.pack(fill=tk.BOTH, expand=True)

        source_list_wrap = ttk.Frame(list_frame)
        source_list_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.source_listbox = tk.Listbox(
            source_list_wrap,
            selectmode=tk.MULTIPLE,
            exportselection=False,
            activestyle="none",
        )
        self.source_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        source_scroll = ttk.Scrollbar(source_list_wrap, orient=tk.VERTICAL, command=self.source_listbox.yview)
        source_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.source_listbox.configure(yscrollcommand=source_scroll.set)

        self.empty_hint = ttk.Label(parent, text="")
        self.empty_hint.pack(fill=tk.X, pady=(4, 8))

        controls = ttk.Frame(parent)
        controls.pack(fill=tk.X)
        self.select_all_button = ttk.Button(controls, text="Select Visible", command=self._select_all)
        self.select_all_button.pack(side=tk.LEFT)
        self.clear_button = ttk.Button(controls, text="Clear", command=self._clear_selection)
        self.clear_button.pack(side=tk.LEFT, padx=(8, 0))

    def _build_results_pane(self, parent: ttk.Frame) -> None:
        """Build status panel, source-quality table, and headline table."""
        top_controls = ttk.Frame(parent)
        top_controls.pack(fill=tk.X, pady=(0, 8))

        self.fetch_button = ttk.Button(top_controls, text="Fetch Latest News", command=self._fetch_latest)
        self.fetch_button.pack(side=tk.LEFT)

        self.cancel_button = ttk.Button(top_controls, text="Cancel", command=self._cancel_fetch, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(top_controls, textvariable=self.last_fetch_var).pack(side=tk.RIGHT)

        status_frame = ttk.LabelFrame(parent, text="Status")
        status_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W, padx=8, pady=(6, 2))
        ttk.Label(status_frame, textvariable=self.progress_var).pack(anchor=tk.W, padx=8, pady=(0, 2))
        ttk.Label(
            status_frame,
            text="Legend: Reliable = strong feed quality, Partial = weak/limited feed, Unavailable = feed failed.",
        ).pack(anchor=tk.W, padx=8, pady=(0, 6))

        source_status_frame = ttk.LabelFrame(parent, text="Per-source quality")
        source_status_frame.pack(fill=tk.X, pady=(0, 8))
        self.status_tree = ttk.Treeview(
            source_status_frame,
            columns=("source", "country", "status"),
            show="headings",
            height=7,
        )
        self.status_tree.heading("source", text="Source")
        self.status_tree.heading("country", text="Country")
        self.status_tree.heading("status", text="Status")
        self.status_tree.column("source", width=220, anchor=tk.W)
        self.status_tree.column("country", width=70, anchor=tk.W)
        self.status_tree.column("status", width=520, anchor=tk.W)
        self.status_tree.pack(fill=tk.X, padx=6, pady=6)

        headlines_frame = ttk.LabelFrame(parent, text="Latest headlines")
        headlines_frame.pack(fill=tk.BOTH, expand=True)

        headline_wrap = ttk.Frame(headlines_frame)
        headline_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.headlines_tree = ttk.Treeview(
            headline_wrap,
            columns=("source", "published", "quality", "title"),
            show="headings",
        )
        self.headlines_tree.heading("source", text="Source")
        self.headlines_tree.heading("published", text="Published (UTC)")
        self.headlines_tree.heading("quality", text="Quality")
        self.headlines_tree.heading("title", text="Headline")
        self.headlines_tree.column("source", width=190, anchor=tk.W)
        self.headlines_tree.column("published", width=160, anchor=tk.W)
        self.headlines_tree.column("quality", width=100, anchor=tk.W)
        self.headlines_tree.column("title", width=640, anchor=tk.W)
        self.headlines_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        headline_scroll = ttk.Scrollbar(headline_wrap, orient=tk.VERTICAL, command=self.headlines_tree.yview)
        headline_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.headlines_tree.configure(yscrollcommand=headline_scroll.set)
        self.headlines_tree.bind("<Double-1>", self._open_selected_headline)

    def _visible_source_id(self, visible_index: int) -> str | None:
        """Return source id for visible list index, or None if index is invalid."""
        if visible_index < 0 or visible_index >= len(self.filtered_indices):
            return None
        source_idx = self.filtered_indices[visible_index]
        return str(self.media_sources[source_idx]["id"])

    def _source_display_name(self, source: dict[str, object]) -> str:
        """Return listbox display name with country indicator."""
        return f"[{source['country']}] {source['name']}"

    def _refresh_source_list(self) -> None:
        """Refresh source list according to search query and country filter."""
        query = self.search_var.get().strip().lower()
        selected_ids = {
            source_id
            for idx in self.source_listbox.curselection()
            if (source_id := self._visible_source_id(int(idx))) is not None
        }

        country = self.country_var.get()
        self.filtered_indices = []
        for idx, source in enumerate(self.media_sources):
            name = str(source["name"]).lower()
            source_country = str(source["country"]) if source.get("country") else ""
            if query and query not in name:
                continue
            if country != "ALL" and source_country != country:
                continue
            self.filtered_indices.append(idx)

        self.source_listbox.delete(0, tk.END)
        for pos, source_idx in enumerate(self.filtered_indices):
            source = self.media_sources[source_idx]
            self.source_listbox.insert(tk.END, self._source_display_name(source))
            if source["id"] in selected_ids:
                self.source_listbox.selection_set(pos)

        if self.filtered_indices:
            self.empty_hint.configure(text=f"{len(self.filtered_indices)} source(s) visible.")
        else:
            self.empty_hint.configure(text="No sources match current search/filter.")

    def _select_all(self) -> None:
        """Select all currently visible sources."""
        self.source_listbox.select_set(0, tk.END)

    def _clear_selection(self) -> None:
        """Clear visible source selection."""
        self.source_listbox.selection_clear(0, tk.END)

    def _apply_preset(self) -> None:
        """Apply selected preset and select matching sources."""
        preset_label = self.preset_var.get()
        preset_id = self.preset_label_to_id.get(preset_label)
        if not preset_id:
            return

        if preset_id == "top_cz":
            self.country_var.set("CZ")
        elif preset_id == "top_sk":
            self.country_var.set("SK")
        else:
            self.country_var.set("ALL")

        self._refresh_source_list()
        self._clear_selection()

        for visible_idx, source_idx in enumerate(self.filtered_indices):
            source = self.media_sources[source_idx]
            if preset_id in source.get("presets", []):
                self.source_listbox.selection_set(visible_idx)

    def _get_selected_sources(self) -> list[dict[str, object]]:
        """Return selected source records from currently visible list items."""
        selected: list[dict[str, object]] = []
        for visible_idx in self.source_listbox.curselection():
            source_idx = self.filtered_indices[int(visible_idx)]
            selected.append(self.media_sources[source_idx])
        return selected

    def _set_fetch_ui_state(self, in_progress: bool) -> None:
        """Enable or disable controls tied to background fetch lifecycle."""
        self.fetch_in_progress = in_progress
        self.fetch_button.configure(state=tk.DISABLED if in_progress else tk.NORMAL)
        self.cancel_button.configure(state=tk.NORMAL if in_progress else tk.DISABLED)
        state = tk.DISABLED if in_progress else tk.NORMAL
        self.search_entry.configure(state=state)
        self.preset_combo.configure(state="disabled" if in_progress else "readonly")
        self.apply_preset_button.configure(state=state)
        self.select_all_button.configure(state=state)
        self.clear_button.configure(state=state)

    def _fetch_latest(self) -> None:
        """Start background feed resolution for selected sources."""
        if self.fetch_in_progress:
            return

        selected_sources = self._get_selected_sources()
        if not selected_sources:
            self.status_var.set("Select at least one source before fetching.")
            return

        self.cancel_event = Event()
        self._set_fetch_ui_state(True)
        self.status_var.set("Fetching and ranking RSS feeds...")
        self.progress_var.set(f"0/{len(selected_sources)} resolved")

        worker = threading.Thread(
            target=self._fetch_worker,
            args=(selected_sources, self.cancel_event),
            daemon=True,
        )
        worker.start()

    def _cancel_fetch(self) -> None:
        """Request cancellation for an in-progress fetch."""
        if self.cancel_event:
            self.cancel_event.set()
            self.status_var.set("Cancel requested. Finishing current source...")

    def _fetch_worker(self, selected_sources: list[dict[str, object]], cancel_event: Event) -> None:
        """Resolve feeds in a worker thread and dispatch UI callbacks safely."""

        def progress(index: int, total: int, result: SourceNewsResult) -> None:
            self._post_ui(lambda: self._handle_progress(index, total, result))

        try:
            per_source_results, items = get_latest_news(
                selected_sources,
                progress_callback=progress,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
                self._post_ui(lambda: self._handle_fetch_cancelled(per_source_results, items))
            else:
                self._post_ui(lambda: self._handle_fetch_success(per_source_results, items))
        except Exception as exc:  # pragma: no cover - defensive UI fallback
            self._post_ui(lambda: self._handle_fetch_error(exc))

    def _post_ui(self, callback: Callable[[], None]) -> None:
        """Schedule a callback only if UI is still alive."""
        if self.is_closing:
            return
        if not self.root.winfo_exists():
            return
        self.root.after(0, callback)

    def _handle_progress(self, index: int, total: int, result: SourceNewsResult) -> None:
        """Update progress line with per-source completion details."""
        self.progress_var.set(f"{index}/{total} resolved ({result.source_name}: {result.status_level})")

    def _update_results(self, per_source_results: list[SourceNewsResult], items: list[NewsItem]) -> None:
        """Render per-source quality and headline tables."""
        for item_id in self.status_tree.get_children():
            self.status_tree.delete(item_id)
        for item_id in self.headlines_tree.get_children():
            self.headlines_tree.delete(item_id)

        source_by_id = {str(source["id"]): source for source in self.media_sources}
        level_by_source_name: dict[str, str] = {}

        for idx, result in enumerate(per_source_results):
            source = source_by_id.get(result.source_id, {})
            country = str(source.get("country", "?"))
            self.status_tree.insert(
                "",
                tk.END,
                iid=f"status-{idx}",
                values=(result.source_name, country, result.status),
            )
            level_by_source_name[result.source_name] = result.status_level

        self.link_map.clear()
        for idx, item in enumerate(items):
            published = item.published.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
            quality = level_by_source_name.get(item.source_name, "unknown")
            item_id = f"headline-{idx}"
            self.headlines_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(item.source_name, published, quality, item.title),
            )
            self.link_map[item_id] = item.link

    def _handle_fetch_success(self, per_source_results: list[SourceNewsResult], items: list[NewsItem]) -> None:
        """Handle successful fetch completion and render data."""
        self._set_fetch_ui_state(False)

        working = sum(1 for result in per_source_results if result.chosen_feed)
        self.status_var.set(f"Done: {working}/{len(per_source_results)} sources resolved.")
        self.last_fetch_var.set(f"Last fetch: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self._update_results(per_source_results, items)
        if not items:
            self.progress_var.set("No headlines available for selected sources.")
        else:
            self.progress_var.set(f"Rendered {len(items)} headline(s). Double-click to open article.")

    def _handle_fetch_cancelled(self, per_source_results: list[SourceNewsResult], items: list[NewsItem]) -> None:
        """Handle cancellation result and show any partial data."""
        self._set_fetch_ui_state(False)
        self.status_var.set("Fetch cancelled by user.")
        self.last_fetch_var.set(f"Last fetch: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (cancelled)")
        self._update_results(per_source_results, items)
        self.progress_var.set("Cancelled. Partial results shown.")

    def _handle_fetch_error(self, exc: Exception) -> None:
        """Handle unexpected worker failure."""
        self._set_fetch_ui_state(False)
        self.status_var.set(f"Fetch failed: {exc}")
        self.progress_var.set("Review source configuration and network availability.")

    def _open_selected_headline(self, _event: object) -> None:
        """Open selected headline URL in default browser."""
        selected = self.headlines_tree.focus()
        if selected and selected in self.link_map:
            webbrowser.open_new_tab(self.link_map[selected])

    def _on_close(self) -> None:
        """Close window and signal any active worker to stop."""
        self.is_closing = True
        if self.cancel_event:
            self.cancel_event.set()
        self.root.destroy()


def main() -> None:
    """Application entry point."""
    root = tk.Tk()
    CzechMediaRssApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
