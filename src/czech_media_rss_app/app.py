from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from datetime import timezone
from tkinter import messagebox, ttk

from .config import MEDIA_SOURCES
from .feeds import NewsItem, SourceNewsResult, get_latest_news


class CzechMediaRssApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Czech Media RSS")
        self.root.geometry("760x520")
        self.root.minsize(680, 460)

        self.media_sources = list(MEDIA_SOURCES)
        self.filtered_indices = list(range(len(self.media_sources)))

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select media and fetch latest news.")
        self.fetch_in_progress = False

        self._build_ui()
        self._refresh_source_list()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(container)
        top.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(top, text="Search media:").pack(side=tk.LEFT)
        search = ttk.Entry(top, textvariable=self.search_var, width=36)
        search.pack(side=tk.LEFT, padx=(8, 8))
        search.bind("<KeyRelease>", lambda _e: self._on_search_changed())

        ttk.Button(top, text="Top Czech News preset", command=self._select_preset).pack(side=tk.RIGHT)

        list_frame = ttk.LabelFrame(container, text="Czech media outlets")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.source_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            exportselection=False,
            height=18,
        )
        self.source_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(controls, text="Select All", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(controls, text="Clear", command=self._clear_selection).pack(side=tk.LEFT, padx=(8, 0))

        self.fetch_button = ttk.Button(controls, text="Fetch Latest News", command=self._fetch_latest)
        self.fetch_button.pack(side=tk.RIGHT)

        ttk.Label(container, textvariable=self.status_var).pack(fill=tk.X, pady=(10, 0))

    def _on_search_changed(self) -> None:
        self._refresh_source_list()

    def _refresh_source_list(self) -> None:
        query = self.search_var.get().strip().lower()
        selected_media_ids = {self._visible_source_id(i) for i in self.source_listbox.curselection()}

        self.filtered_indices = []
        for idx, source in enumerate(self.media_sources):
            name = source["name"].lower()
            if query and query not in name:
                continue
            self.filtered_indices.append(idx)

        self.source_listbox.delete(0, tk.END)
        for pos, source_idx in enumerate(self.filtered_indices):
            source = self.media_sources[source_idx]
            self.source_listbox.insert(tk.END, source["name"])
            if source["id"] in selected_media_ids:
                self.source_listbox.selection_set(pos)

    def _visible_source_id(self, visible_index: int) -> str:
        source_idx = self.filtered_indices[visible_index]
        return self.media_sources[source_idx]["id"]

    def _select_all(self) -> None:
        self.source_listbox.select_set(0, tk.END)

    def _clear_selection(self) -> None:
        self.source_listbox.selection_clear(0, tk.END)

    def _select_preset(self) -> None:
        preset = {"ct24", "idnes", "novinky", "seznam_zpravy", "aktualne"}
        self.source_listbox.selection_clear(0, tk.END)
        for visible_idx, source_idx in enumerate(self.filtered_indices):
            if self.media_sources[source_idx]["id"] in preset:
                self.source_listbox.selection_set(visible_idx)

    def _get_selected_sources(self) -> list[dict]:
        selected = []
        for visible_idx in self.source_listbox.curselection():
            source_idx = self.filtered_indices[visible_idx]
            selected.append(self.media_sources[source_idx])
        return selected

    def _fetch_latest(self) -> None:
        if self.fetch_in_progress:
            return

        selected_sources = self._get_selected_sources()
        if not selected_sources:
            messagebox.showwarning("No selection", "Please select at least one media source.")
            return

        self.fetch_in_progress = True
        self.fetch_button.configure(state=tk.DISABLED)
        self.status_var.set("Fetching and ranking RSS feeds...")

        worker = threading.Thread(
            target=self._fetch_worker,
            args=(selected_sources,),
            daemon=True,
        )
        worker.start()

    def _fetch_worker(self, selected_sources: list[dict]) -> None:
        try:
            per_source_results, items = get_latest_news(selected_sources)
            self.root.after(0, lambda: self._handle_fetch_success(per_source_results, items))
        except Exception as exc:
            self.root.after(0, lambda: self._handle_fetch_error(exc))

    def _handle_fetch_success(self, per_source_results: list[SourceNewsResult], items: list[NewsItem]) -> None:
        self.fetch_in_progress = False
        self.fetch_button.configure(state=tk.NORMAL)

        working = sum(1 for result in per_source_results if result.chosen_feed)
        self.status_var.set(f"Done: {working}/{len(per_source_results)} sources resolved.")

        if not items:
            details = "\n".join(f"- {result.source_name}: {result.status}" for result in per_source_results)
            messagebox.showerror("No headlines available", details)
            return

        self._show_news_dialog(per_source_results, items)

    def _handle_fetch_error(self, exc: Exception) -> None:
        self.fetch_in_progress = False
        self.fetch_button.configure(state=tk.NORMAL)
        self.status_var.set("Failed to fetch feeds.")
        messagebox.showerror("Fetch error", str(exc))

    def _show_news_dialog(self, per_source_results: list[SourceNewsResult], items: list[NewsItem]) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Latest Czech Media Headlines")
        dialog.geometry("960x560")
        dialog.minsize(820, 480)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        summary = ttk.Frame(frame)
        summary.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(summary, text="Feed quality:").pack(side=tk.LEFT)
        statuses = " | ".join(f"{result.source_name}: {result.status}" for result in per_source_results)
        ttk.Label(summary, text=statuses, wraplength=900).pack(side=tk.LEFT, padx=(8, 0))

        tree = ttk.Treeview(
            frame,
            columns=("source", "published", "title"),
            show="headings",
            height=20,
        )
        tree.heading("source", text="Source")
        tree.heading("published", text="Published (UTC)")
        tree.heading("title", text="Headline")
        tree.column("source", width=170, anchor=tk.W)
        tree.column("published", width=180, anchor=tk.W)
        tree.column("title", width=570, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True)

        link_map: dict[str, str] = {}
        for idx, item in enumerate(items):
            published = item.published.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
            item_id = f"item-{idx}"
            tree.insert("", tk.END, iid=item_id, values=(item.source_name, published, item.title))
            link_map[item_id] = item.link

        def open_selected(_event: object) -> None:
            selected = tree.focus()
            if selected and selected in link_map:
                webbrowser.open_new_tab(link_map[selected])

        tree.bind("<Double-1>", open_selected)

        footer = ttk.Frame(frame)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(footer, text="Double-click a headline to open it in your browser.").pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)


def main() -> None:
    root = tk.Tk()
    app = CzechMediaRssApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

