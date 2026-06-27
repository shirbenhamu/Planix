# src/MVP/app_controller.py

import threading
import time

# Robust multi-environment import resolution pattern to bypass Windows pytest collection issues
try:
    from MVP.models.planix_model import PlanixModel
    from MVP.models.schedule_collection_manager import ScheduleCollectionManager
    from MVP.presenters.input_presenter import InputPresenter
    from MVP.presenters.calendar_presenter import CalendarPresenter
    from engine.engine_adapter import PlanixEngineAdapter
except ModuleNotFoundError:
    from src.MVP.models.planix_model import PlanixModel
    from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
    from src.MVP.presenters.input_presenter import InputPresenter
    from src.MVP.presenters.calendar_presenter import CalendarPresenter
    from src.engine.engine_adapter import PlanixEngineAdapter


class AppController:
    def __init__(self, app_window, data_manager):
        self.app_window = app_window
        self.data_manager = data_manager

        # Initialize core application single source of truth state context
        self.model = PlanixModel(data_manager=self.data_manager)
        self.engine_adapter = PlanixEngineAdapter()

        self.output_path = "output_results/final_schedules.txt"
        # Deep search ("Find best") writes only its top-N to a SEPARATE file so
        # the set already on screen stays browsable while it runs; it is swapped
        # in only when finished. The total count and scanned progress come back
        # over in-memory IPC (no temp files).
        self.load_all_output_path = "output_results/final_schedules_all.txt"
        self._total_count = None
        self._all_loaded = False
        # Deep-search run state (for the time-based meter and the start/cancel toggle).
        self._deep_search_active = False
        self._deep_search_started = None
        self.collection_manager = ScheduleCollectionManager(
            output_file_path=self.output_path, data_manager=data_manager)

        # Instantiate presenters
        self.input_presenter = InputPresenter(
            view=self.app_window.input_view, model=self.model)
        self.calendar_presenter = CalendarPresenter(
            view=self.app_window.calendar_view,
            model=self.model,
            collection_manager=self.collection_manager
        )
        
        # PLAN-405: Inject parent router controller reference into input presenter
        self.input_presenter.controller = self
        
        self.app_window.wire_sync_callback(self.calendar_presenter)
        self.calendar_presenter.controller = self
        self._wire_constraints_settings_callbacks()
        
        self.app_window.monthly_view.on_range_update_clicked = self.calendar_presenter._handle_range_update
        self.app_window.input_view.on_range_update_clicked = self.calendar_presenter._handle_range_update

        # Load All (compute the full solution space in the background).
        for view in (self.app_window.calendar_view, self.app_window.monthly_view):
            if hasattr(view, "on_load_all_clicked"):
                view.on_load_all_clicked = self.load_all_schedules

        self.app_window.on_navigation_requested = self._handle_navigation
        self._handle_navigation("input")

    def _wire_constraints_settings_callbacks(self) -> None:
        """Connects PLAN-418 settings buttons from all screens to the single presenter/model state."""
        for view in (
            getattr(self.app_window, "input_view", None),
            getattr(self.app_window, "calendar_view", None),
            getattr(self.app_window, "monthly_view", None),
        ):
            if view is not None and hasattr(view, "on_save_constraints"):
                view.on_save_constraints = self._handle_constraints_settings_save

        self._broadcast_constraints_state(self._constraints_data_from_model())
        self._set_constraints_save_state(enabled=True)

    def _constraints_data_from_model(self) -> dict:
        constraints = self.model.constraints
        return {
            "min_days_mandatory_enabled": constraints.min_days_mandatory_enabled,
            "min_days_mandatory_k": constraints.min_days_mandatory_k,
            "min_days_any_enabled": constraints.min_days_any_enabled,
            "min_days_any_k": constraints.min_days_any_k,
            "max_elective_conflicts_enabled": constraints.max_elective_conflicts_enabled,
            "max_elective_conflicts_k": constraints.max_elective_conflicts_k,
            "span_mandatory_enabled": constraints.span_mandatory_enabled,
            "span_mandatory_k": constraints.span_mandatory_k,
            "max_exams_per_day_enabled": constraints.max_exams_per_day_enabled,
            "max_exams_per_day_k": constraints.max_exams_per_day_k,
        }

    def _broadcast_constraints_state(self, constraints_data: dict) -> None:
        for view in (
            getattr(self.app_window, "input_view", None),
            getattr(self.app_window, "calendar_view", None),
            getattr(self.app_window, "monthly_view", None),
        ):
            if view is not None and hasattr(view, "set_constraints_data"):
                view.set_constraints_data(constraints_data)

    def _set_constraints_save_state(self, enabled: bool) -> None:
        for view in (
            getattr(self.app_window, "input_view", None),
            getattr(self.app_window, "calendar_view", None),
            getattr(self.app_window, "monthly_view", None),
        ):
            if view is not None and hasattr(view, "set_save_button_state"):
                view.set_save_button_state(enabled)

    def _handle_constraints_settings_save(self, constraints_data: dict) -> None:
        if self.engine_adapter.is_generation_active():
            self._set_constraints_save_state(enabled=False)
            print("[AppController][Block] Constraints settings save denied while generation is active.")
            return

        self._broadcast_constraints_state(constraints_data)
        self.input_presenter._handle_save_constraints(constraints_data)

    def _handle_navigation(self, target_view: str) -> None:
        if target_view == "calendar":
            self.regenerate_schedules_snapshot()
            return
        self.app_window.switch_view(target_view)

    def regenerate_schedules_snapshot(self) -> None:
        """
        Acceptance Criteria Met: Updated to follow UI Lock design pattern.
        If an active background process is currently running, safely direct the user
        straight to the active calendar snapshot results instead of an aggressive termination rerun.
        """
        print("[AppController] Request received to evaluate schedule snapshot pipeline...")
            
        if not self.model.get_selected_programs():
            print("[AppController] No programs selected. Skipping generation.")
            self.collection_manager.clear_cache()
            self._set_constraints_save_state(enabled=True)
            return
        
        self.collection_manager.clear_cache()
        self._set_constraints_save_state(enabled=False)
        # A fresh run replaces any prior deep-search result: drop the
        # "best 100K…" message and the stale remaining count immediately, rather
        # than leaving them until the next background count finishes.
        self._all_loaded = False
        self._total_count = None
        view = getattr(getattr(self, "calendar_presenter", None), "view", None)
        if view is not None and hasattr(view, "clear_load_indicators"):
            view.clear_load_indicators()
        self.app_window.switch_view("annual")

        if self.engine_adapter.is_generation_active():
            print("[AppController] Active generation detected. Reusing it; routing to calendar snapshot.")
            self.app_window.switch_view("calendar")
            self.app_window.after(100, self._load_snapshot_schedules)
            return
        
        print("[AppController] Engine idle. Initiating clean schedule generation pipeline...")
        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False
        self.collection_manager.snapshot_mode = False
        
        output_path = getattr(self, "output_path", "output_results/final_schedules.txt")
        # Launch new Advanced engine generation with the updated SchedulingConstraints setup
        self.engine_adapter.generate_from_model(
            model=self.model, output_path=output_path)
            
        self.app_window.switch_view("calendar")
        self.app_window.after(100, self._load_snapshot_schedules)

    def _load_snapshot_schedules(self) -> None:
        prev_count = self.collection_manager.get_total_count()
        self.collection_manager.build_snapshot_index()
        current_count = self.collection_manager.get_total_count()
        
        if prev_count == 0 and current_count > 0:
            self.calendar_presenter.refresh_presenter_state()
        else:
            self.calendar_presenter.refresh_pagination_only()

        if self.engine_adapter.is_generation_active():
            self.app_window.after(500, self._load_snapshot_schedules)
        else:
            self.collection_manager.snapshot_mode = False
            self.collection_manager.apply_sort_and_refresh(reset_to_top=False)
            if hasattr(self.model, "is_generating") and self.model.is_generating:
                self.model.is_generating = False
            self.engine_adapter.clear_finished_worker()
            self._set_constraints_save_state(enabled=True)
            self.calendar_presenter.refresh_presenter_state()
            print("[AppController] Engine idle. Snapshot mode disabled for full file access.")
            # A fresh normal run replaces any prior deep-search result: re-enable
            # Load More and the deep-search button (a previous deep search may
            # have retired them), then (re)count the space for the indicator.
            self._all_loaded = False
            view = getattr(self.calendar_presenter, "view", None)
            if view is not None:
                if hasattr(view, "set_load_more_enabled"):
                    view.set_load_more_enabled(True)
                if hasattr(view, "set_load_all_enabled"):
                    view.set_load_all_enabled(True)
            self.start_total_count()

    def load_more_schedules(self, skip_count: int) -> None:
        if self.engine_adapter.is_generation_active():
            print("[AppController] Generation process is already active. Request denied.")
            return

        print(f"[AppController] Activating 'Load More' pipeline. Skip target: {skip_count}")
        self._set_constraints_save_state(enabled=False)
        if hasattr(self.model, "is_generating"):
            self.model.is_generating = True
        self.collection_manager.snapshot_mode = True

        self.engine_adapter.generate_from_model(
            model=self.model,
            output_path=self.output_path,
            skip_count=skip_count
        )
        self.app_window.after(
            500, lambda: self._monitor_load_more_progress(previous_count=skip_count))

    def _monitor_load_more_progress(self, previous_count: int) -> None:
        self.collection_manager.build_snapshot_index()
        self.calendar_presenter.refresh_pagination_only()

        if self.engine_adapter.is_generation_active():
            self.app_window.after(
                500, lambda: self._monitor_load_more_progress(previous_count))
        else:
            self.collection_manager.snapshot_mode = False
            self.collection_manager.apply_sort_and_refresh(reset_to_top=False)
            if hasattr(self.model, "is_generating") and self.model.is_generating:
                self.model.is_generating = False

            self.engine_adapter.clear_finished_worker()
            self._set_constraints_save_state(enabled=True)
            self.calendar_presenter.refresh_presenter_state()
            print("[AppController] Load More background worker has finished execution.")

            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    final_count = f.read().count("--- FULL SYSTEM OPTION")
                if final_count == previous_count:
                    if hasattr(self.calendar_presenter.view, "show_no_more_results"):
                        self.calendar_presenter.view.show_no_more_results()
            except Exception as e:
                print(f"[AppController] Error evaluating post-run final counts: {e}")

            # Load More added schedules: the TOTAL is unchanged (same
            # constraints), only 'loaded' grew — so refresh the remaining count
            # immediately instead of re-running the count pass.
            if getattr(self, "_total_count", None) is not None:
                self._update_remaining_indicator()
            else:
                self.start_total_count()

    # ===== Total-count indicator ("X schedules remaining to load") ============

    def start_total_count(self) -> None:
        """Kick off a background pass that counts the total number of valid
        schedules, then refresh the remaining-to-load indicator once it lands.
        Skipped once everything is already loaded (Load All has run)."""
        if getattr(self, "_all_loaded", False):
            return
        get_programs = getattr(self.model, "get_selected_programs", None)
        if not callable(get_programs) or not get_programs():
            return
        if self.engine_adapter.is_count_active():
            return
        try:
            self.engine_adapter.count_total_from_model(self.model)
        except Exception as e:
            print(f"[AppController] Could not start total-count pass: {e}")
            return
        # Give immediate feedback on the Load More tooltip while the count runs,
        # so it isn't blank until the background pass finishes.
        view = getattr(self.calendar_presenter, "view", None)
        if view is not None and hasattr(view, "set_load_more_calculating"):
            view.set_load_more_calculating()
        self.app_window.after(500, self._poll_total_count)

    def _poll_total_count(self) -> None:
        if self.engine_adapter.is_count_active():
            self.app_window.after(500, self._poll_total_count)
            return
        total = self.engine_adapter.read_total_count()
        if total is not None:
            self._total_count = total
        self._update_remaining_indicator()

    def _update_remaining_indicator(self) -> None:
        """Tell the view how many schedules are still loadable beyond the ones
        already on screen: remaining = total - currently loaded."""
        total = getattr(self, "_total_count", None)
        if total is None:
            return
        loaded = self.collection_manager.get_total_count()
        remaining = max(0, total - loaded)
        view = getattr(self.calendar_presenter, "view", None)
        if view is not None and hasattr(view, "update_remaining_indicator"):
            view.update_remaining_indicator(
                remaining=remaining,
                total=total,
                loaded=loaded,
                all_loaded=getattr(self, "_all_loaded", False) or remaining == 0,
            )

    # ===== Deep search: keep the top-N best across a bounded scan =============

    # How many best schedules to keep (bounds disk), and the TIME budget for the
    # scan (bounds wall-clock and drives a real 0->100% meter). Scanning is cheap
    # (no disk writes), so a few minutes covers a large slice of the space.
    DEEP_SEARCH_TOP_N = 100_000
    DEEP_SEARCH_MAX_SECONDS = 600  # 10 minutes

    def _deep_search_view(self):
        return getattr(self.calendar_presenter, "view", None)

    def _lock_engine_triggers(self, locked: bool) -> None:
        """Disable/enable the buttons that kick off the engine (input START and
        the Sync buttons) across every screen while a deep search runs, so the
        user can't launch a conflicting engine run mid-search. Cancelling the
        deep search (✕) re-enables them."""
        enabled = not locked
        input_view = getattr(self.app_window, "input_view", None)
        if input_view is not None and hasattr(input_view, "btn_run"):
            try:
                input_view.btn_run.configure(state="disabled" if locked else "normal")
            except Exception:
                pass
        for view_name in ("calendar_view", "monthly_view"):
            view = getattr(self.app_window, view_name, None)
            toolbar = getattr(view, "toolbar", None) if view is not None else None
            if toolbar is not None and hasattr(toolbar, "set_sync_enabled"):
                try:
                    toolbar.set_sync_enabled(enabled)
                except Exception:
                    pass

    def load_all_schedules(self) -> None:
        """Start (or cancel) a deep search for the best schedules.

        Clicking while idle starts it; clicking while it runs CANCELS it (the
        button toggles to 'Cancel deep search'). The search streams full-year
        combinations for up to DEEP_SEARCH_MAX_SECONDS, keeps only the
        DEEP_SEARCH_TOP_N best for the active sort, and writes just those to a
        separate file. The user keeps browsing the set already on screen
        meanwhile; a time-based percentage meter reports progress. When it
        finishes, the best set is swapped in and shown.
        """
        # Toggle: a second click cancels the running search.
        if self._deep_search_active:
            self._cancel_deep_search()
            return

        if self.engine_adapter.is_generation_active():
            print("[AppController] Generation already active. Deep search denied.")
            return
        if not self.model.get_selected_programs():
            print("[AppController] No programs selected. Deep search skipped.")
            return

        print("[AppController] Deep search requested. Scanning for the best schedules...")
        self._deep_search_active = True
        self._deep_search_started = time.time()
        self._set_constraints_save_state(enabled=False)
        self._lock_engine_triggers(True)   # no engine runs while the search works
        if hasattr(self.model, "is_generating"):
            self.model.is_generating = True

        view = self._deep_search_view()
        if view is not None:
            if hasattr(view, "set_load_more_enabled"):
                view.set_load_more_enabled(False)   # retire Load More during the search
            if hasattr(view, "set_load_all_running"):
                view.set_load_all_running(True)      # button -> 'Cancel deep search'

        sort_spec = self.collection_manager.get_active_sort_spec()
        self.engine_adapter.deep_search_from_model(
            self.model,
            output_path=self.load_all_output_path,
            sort_spec=sort_spec,
            top_n=self.DEEP_SEARCH_TOP_N,
            max_seconds=self.DEEP_SEARCH_MAX_SECONDS,
        )
        self.app_window.after(500, self._monitor_load_all_progress)

    def _deep_search_percent(self) -> float:
        # Time-based: how much of the wall-clock budget has elapsed. Meaningful
        # even when the space is astronomically large (a count-based % would
        # always read ~0).
        started = self._deep_search_started
        if not started or self.DEEP_SEARCH_MAX_SECONDS <= 0:
            return 0.0
        return min(100.0, (time.time() - started) / self.DEEP_SEARCH_MAX_SECONDS * 100.0)

    def _monitor_load_all_progress(self) -> None:
        if not self._deep_search_active:
            return  # cancelled — stop polling, finalize already handled by cancel

        view = self._deep_search_view()
        if self.engine_adapter.is_generation_active():
            # Progress only — do NOT touch the on-screen collection; the user
            # keeps browsing the existing set until the best set is swapped in.
            percent = self._deep_search_percent()
            if view is not None:
                # Once the time budget is spent the worker is writing the top-N;
                # show 'Saving results…' instead of a frozen 100%.
                if percent >= 100.0 and hasattr(view, "set_load_all_saving"):
                    view.set_load_all_saving()
                elif hasattr(view, "set_load_all_progress"):
                    view.set_load_all_progress(percent)
            self.app_window.after(500, self._monitor_load_all_progress)
            return

        # Finished normally: swap the best-N file in and show it.
        import os
        try:
            os.replace(self.load_all_output_path, self.output_path)
        except OSError as e:
            print(f"[AppController] Could not swap in the best-schedules file: {e}")

        self._deep_search_active = False
        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False
        self.engine_adapter.clear_finished_worker()
        self._set_constraints_save_state(enabled=True)
        self._lock_engine_triggers(False)   # engine runs allowed again

        scanned = self.engine_adapter.read_deep_search_scanned()

        self.collection_manager.snapshot_mode = False
        self.collection_manager.clear_cache()
        self._all_loaded = True
        kept = self.collection_manager.get_total_count()
        self._total_count = kept
        self.collection_manager.apply_sort_and_refresh(reset_to_top=True)
        self.calendar_presenter.refresh_presenter_state()

        if view is not None:
            if hasattr(view, "set_load_all_running"):
                view.set_load_all_running(False)     # button -> magnifying glass
            if hasattr(view, "set_load_more_enabled"):
                view.set_load_more_enabled(False)    # the best set is final
            # The best 100K are found; a new deep search only makes sense after
            # the engine re-runs (e.g. a constraints change). Block it until then.
            if hasattr(view, "set_load_all_enabled"):
                view.set_load_all_enabled(False)
            # Summary of the value delivered: how many were scanned for the kept best-N.
            if hasattr(view, "set_deep_search_done"):
                view.set_deep_search_done(scanned, kept)
        print(f"[AppController] Deep search finished. Scanned {scanned}, kept best {kept}.")

    def _cancel_deep_search(self) -> None:
        """User cancelled: kill the worker, discard partial results, and restore
        the UI to its pre-search state."""
        print("[AppController] Deep search cancelled by user.")
        self._deep_search_active = False
        self.engine_adapter.cancel_active_worker()
        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False
        self._set_constraints_save_state(enabled=True)
        self._lock_engine_triggers(False)   # engine runs allowed again

        view = self._deep_search_view()
        if view is not None:
            if hasattr(view, "set_load_all_running"):
                view.set_load_all_running(False)     # button -> 'Find best'
            if hasattr(view, "set_load_all_progress"):
                view.set_load_all_progress(0.0)
            if hasattr(view, "set_load_more_enabled"):
                view.set_load_more_enabled(True)     # Load More is available again
        self._update_remaining_indicator()