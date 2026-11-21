# Accessibility checks in COBOL Coroner

This file lists the accessibility checks the repository runs, the checks made by hand in a browser, and the limits of both. Each check names the test function that runs it, or the review entry in [`docs/reviews.md`](reviews.md) that records the manual check. The project does not claim conformance to any accessibility standard.

## 1. Scope

The pages below are the ones with accessibility checks. Coverage differs from page to page, and the gaps are listed in section 4.

- **Guided story** (`/story`, `/story/step/1` to `/story/step/8`, in the Business and Engineer views): the most complete coverage. Form labels, live regions, focus after a step change, the keyboard script, text without JavaScript, status shapes, contrast of the story colours and the 375 px rules are all checked.
- **"Can you fool Coroner?"** (`/fool`): form labels, one live region for the result, a plain GET form with a noscript Update button, status shapes with text, and the counter without JavaScript.
- **Home page** (`/`): the Recent Runs region (labelled, focusable, in a scrolling box), the 375 px layout in a real browser, and the story and fool links. The Run audit form is not in the label checks.
- **Run page** (`/run/<run id>`, ZOMBIE, ALIVE and ERROR): colour contrast in dark and light mode, the ERROR diamond shape, and the contrast of the chart bars. No label, keyboard or focus check.
- **Detection Matrix** (`/matrix`): no accessibility check. The page extends the shared base template, whose colour variables the contrast tests read.
- **Tamper** (`/tamper`): no accessibility check on the standalone page. Its form has labels and a focus style in `coroner/ui/templates/tamper.html`, but no test asserts them. The same form inside story step 8 is checked for labels.

## 2. What the automated tests check

Tests marked `slow` use real runs (fixtures `story_runs`, `fool_runs`, `story_client`, `fool_client`) or start a browser. The other tests need no run and use an empty base directory.

| Check | Pages | Test file | Test name |
|---|---|---|---|
| Positioning sentence on every story and fool page | Story, fool | tests/test_story_a11y.py | test_positioning_sentence_is_on_every_page_type |
| Positioning sentence on every story step with real runs | Story | tests/test_story_a11y.py | test_positioning_sentence_is_on_every_story_page_with_real_runs |
| Next and Back are links with an href, not buttons | Story | tests/test_story_a11y.py | test_next_and_back_are_links_with_an_href |
| Next and Back without JavaScript lead to the neighbouring step | Story | tests/test_story_a11y.py | test_following_next_and_back_without_javascript_gives_the_neighbouring_step |
| Next and Back and the view links carry the view and target the content region | Story | tests/test_story_shell.py | test_next_and_back_carry_the_view_and_are_links |
| The view links are a navigation labelled "View", and the current one has aria-current | Story | tests/test_story_shell.py | test_full_page_has_positioning_sentence_step_counter_and_view_links |
| Every step title is a focusable heading (tabindex -1), so focus can move to it | Story | tests/test_story_shell.py | test_every_step_has_its_title_as_a_focusable_heading |
| Each async result container is empty and its swapped result is the one live region (steps 4, 7, 8) | Story | tests/test_story_a11y.py | test_every_async_target_of_the_story_is_a_container_whose_swapped_result_is_a_live_region |
| Each result container is not a live region itself, and the swapped result adds exactly one | Story | tests/test_story_shell.py | test_every_story_result_container_is_empty_and_not_a_live_region_itself |
| Each result container holds exactly one live region once the fragment is swapped in | Story | tests/test_story_shell.py | test_every_story_result_has_exactly_one_live_region_once_swapped_in |
| The gate result on a real step page is announced by exactly one live region | Story | tests/test_story_fragments.py | test_gate_result_is_announced_by_exactly_one_live_region_on_the_real_step_page |
| A failing action returns a role="alert" fragment | Story | tests/test_story_a11y.py | test_a_failing_action_gives_an_alert_the_visitor_hears |
| The fool result region is the one live region; its fragment has none | Fool | tests/test_story_a11y.py | test_the_fool_result_region_is_the_one_live_region_and_its_fragment_has_none |
| The fool result container is a status region with aria-live="polite" | Fool | tests/test_story_fool.py | test_exactly_one_live_region_for_the_toggle_result_the_page_container |
| The htmx counter fragment on real runs has no live region | Fool | tests/test_story_fool.py | test_htmx_fragment_for_real_runs_has_the_counter_and_no_live_region |
| Each listing region is focusable (tabindex 0) and its aria-label names the file and the lines | Story (steps 1 and 6) | tests/test_story_a11y.py | test_every_listing_region_has_tabindex_and_an_aria_label_naming_file_and_lines |
| Every form control has a label or aria-label, and every button has text (no run needed) | Fool, story (steps 1, 2, 3, 5, 6) | tests/test_story_a11y.py | test_every_control_has_a_label_without_runs |
| Every control of every story step has a label, including the run and tamper fields | Story (steps 1 to 8) | tests/test_story_a11y.py | test_every_control_of_every_story_step_has_a_label |
| Every toggle of the fool page has a label | Fool | tests/test_story_a11y.py | test_every_toggle_of_the_fool_page_has_a_label |
| Each status has its own shape, marked aria-hidden, and the text carries the meaning | Story, fool | tests/test_story_a11y.py | test_each_status_has_its_own_shape |
| Result badges have a shape and a text label | Story | tests/test_story_a11y.py | test_result_badges_have_a_shape_and_a_text_label |
| The verdict badges of steps 4 and 7 have a shape and the word ZOMBIE or ALIVE | Story | tests/test_story_a11y.py | test_the_verdict_badges_of_steps_4_and_7_have_shape_and_word |
| Every badge of the fool page has a shape and a word | Fool | tests/test_story_a11y.py | test_every_badge_of_the_fool_page_has_shape_and_word |
| Every story step page is complete without htmx (full HTML, text, links) | Story | tests/test_story_nojs.py | test_every_step_page_is_complete_without_htmx |
| Each action form has a noscript note right after its result container | Story (steps 4, 7, 8) | tests/test_story_nojs.py | test_every_action_form_has_a_noscript_note_right_after_its_result_container |
| The fool form is a plain GET form with a noscript Update button | Fool | tests/test_story_nojs.py | test_the_fool_form_is_a_plain_get_form_with_an_update_button_for_noscript |
| The fool counter is correct with GET parameters and no script | Fool | tests/test_story_nojs.py | test_the_get_form_with_parameters_shows_the_right_counter |
| The keyboard script has the modifier, input and region guards, and handles the arrow keys, Escape and the focus move | Story | tests/test_story_shell.py | test_story_js_is_served_and_has_the_guards_the_spec_describes |
| The story template has no inline script and loads the script deferred | Story | tests/test_story_shell.py | test_story_template_has_no_inline_script_and_loads_story_js_deferred |
| Story text colours reach the contrast ratio of 4.5:1 on both backgrounds, in dark and light mode | Story (and the fool page, which shares the stylesheet) | tests/test_story_shell.py | test_home_story_colors_keep_the_contrast_ratios_of_the_ui_tests |
| The story stylesheet uses only theme variables, with no fixed colour | Fool | tests/test_story_shell.py | test_home_story_stylesheet_uses_only_the_variables_of_the_page_theme |
| Story, fool and home pages carry the 375 px rules (tap targets, 16 px text, one column, scrolling tables) | Home, story, fool | tests/test_story_shell.py | test_home_story_and_fool_pages_carry_the_375_px_rules |
| Home page has no horizontal overflow at 375 px (real browser) | Home | tests/test_ui_home_375.py | test_home_page_has_no_horizontal_overflow_at_375_px |
| Recent Runs table is inside a scrolling box at 375 px (real browser) | Home | tests/test_ui_home_375.py | test_recent_runs_table_is_inside_a_scrolling_box_at_375_px |
| Run audit form stays inside the screen at 375 px (real browser) | Home | tests/test_ui_home_375.py | test_run_audit_form_stays_inside_the_screen_at_375_px |
| Recent Runs region is labelled by its heading, focusable, and has a caption that says it scrolls | Home | tests/test_story_shell.py | test_recent_runs_table_sits_in_a_scrollable_labelled_region |
| The scrolling box has a focus outline | Home | tests/test_story_shell.py | test_recent_runs_wrapper_scrolls_inside_its_box_and_shows_a_focus_outline |
| Text and background colours of the run page reach 4.5:1, dark mode | Run | tests/test_ui_pages.py | test_css_contrast_ratios_dark_mode |
| Text and background colours of the run page reach 4.5:1, light mode | Run | tests/test_ui_pages.py | test_css_contrast_ratios_light_mode |
| Base template colour pairs (text, ALIVE, ZOMBIE, ERROR) reach 4.5:1 | Run and every page that extends the base template | tests/test_ui_app.py | test_wcag_contrast_ratios |
| ERROR text and background reach 4.5:1 in both modes | Run (ERROR) | tests/test_ui_error.py | test_error_color_contrast |
| The ERROR badge is a rotated square (diamond) | Run (ERROR) | tests/test_ui_error.py | test_error_diamond_shape |
| Chart bars reach 3:1 against the panel background | Run | tests/test_ui_run_page_fixes.py | test_chart_color_contrast |
| Every README image has non-empty alt text, and the demo GIF is under 5 MB | README (not a page) | tests/test_screenshots_static.py | test_readme_images_exist |

The tests of the form labels, the live regions and the badges were first written for the guided story. R-142 records that a deliberate removal of a `for` attribute made the label test fail, and it was restored. R-137 and R-138 record that the agent checked deliberate mutations against the tests of the step pages.

## 3. Checked by hand in a browser

The browser checks ran in headless Chrome through Playwright, against a local server with real runs. The review log records no other browser, no other operating system and no screen reader session.

- **Keyboard on the story (R-137, operator, served story):** ArrowRight and ArrowLeft move between steps 1 and 2 and update the title. Focus lands on the step heading. Tab reaches Next, and Enter follows it. The positioning sentence is on the page. Step 2 shows the transaction count and the branch subtotals, and step 3 shows both grand totals in the Engineer view. The screenshots of that session timed out, so the checks read the page text.
- **Fool page (R-141, operator, served page):** checking the three boxes changed the counter in the browser (unchecking Case 2 changed it from 3 to 2 of 2 in that session). The review entry records the counter values, not the keyboard.
- **375 px, no horizontal overflow (R-141, operator):** story steps 1, 2, 4, 5 and 8, and `/fool`.
- **375 px, no horizontal overflow (R-142, operator):** `/`, `/fool`, `/matrix`, and story steps 1, 4, 5, 7 and 8. R-142 also records that the story header shows the case name at this width.
- **Gate result (R-138, operator):** on story step 4, the gate button ran the real replay in 16.1 s. The live region announced "This ZOMBIE migration cannot be committed" and "Exit code 1".
- **Step 5 (R-138, operator, Engineer view):** the two branches that do not reconcile, the suspense amount, the cause of death, the COBOL rule with its line numbers and the four exhibits are on the page.

### Findings fixed after the browser checks

- **The gate result was in two live regions (R-138, found by the operator).** The container and the swapped fragment were both live. R-141 fixed it: the swapped fragment is the only live region. The tests `test_gate_result_is_announced_by_exactly_one_live_region_on_the_real_step_page` and `test_every_story_result_has_exactly_one_live_region_once_swapped_in` check it.
- **The home page overflowed by 26 px at 375 px (R-141, operator).** The Recent Runs table was wider than the screen. R-142 put the table in a `.table-scroll` box, and R-162 added `test_home_page_has_no_horizontal_overflow_at_375_px`. R-162 also records that without the box the page measured 381 px and the test failed.

## 4. Known limits

These limits come from the test files, the templates and the review log.

- **No screen reader was used.** The review log records no session with a screen reader. The live regions and the focus move are tested in the markup and checked in the browser, not by a screen reader's output.
- **Keyboard behaviour is tested by its source code only.** `test_story_js_is_served_and_has_the_guards_the_spec_describes` looks for words in `story.js` (the guards, the key names, the handler names). No test runs the script. The arrow keys, Escape and the focus move were checked by hand (section 3).
- **No check with JavaScript switched off in a browser.** The no-JavaScript tests send plain GET requests and read the HTML. They show that the text and the links are in the server output. No browser with scripting disabled was run.
- **Contrast is tested on some pages only.** The story colour test reads the colour variables of the story step 1 page. The run page tests read the variables of the run page. The matrix, tamper and home pages have no direct contrast test; they share the base template colours, which `test_wcag_contrast_ratios` reads from `coroner/ui/templates/base.html`.
- **Two contrast tests use fixed colours or a simpler formula.** `test_error_color_contrast` types the ERROR colours in the test body instead of reading them from the template. `test_chart_color_contrast` computes a simplified luminance and a 3:1 threshold, not the full relative-luminance formula used by the other contrast tests.
- **The chart colours are not checked against the text.** The chart test checks the bar colours against the panel background only.
- **No check of the standalone tamper page.** Its labels and focus style in `coroner/ui/templates/tamper.html` have no test. `test_ui_tamper.py` tests the tamper behaviour, not its markup.
- **No check of the matrix page.** `/matrix` has no accessibility test. Its table headers are not checked.
- **No check of the run page keyboard or labels.** The run page has contrast tests, and nothing else for accessibility.
- **The home page Run audit form has no label test.** `index.html` labels the sample, port and seed fields. The label tests cover the fool page and the story steps (`test_every_control_has_a_label_without_runs` and `test_every_control_of_every_story_step_has_a_label`), but not `/`.
- **The 375 px check is automated for the home page only.** The story and fool pages have CSS rule tests (`test_home_story_and_fool_pages_carry_the_375_px_rules`), which check that the rules exist, not the layout. Their widths were checked by hand (section 3).
- **Alt text is checked for presence only.** `test_readme_images_exist` checks that each README image has non-empty alt text. It does not check what the text says. No UI template contains an `<img>` element.
- **Print and reduced motion are not tested.** `coroner/ui/templates/base.html` has a print stylesheet and a `prefers-reduced-motion` rule. No test checks either.
- **Zoom and text scaling are not tested.** No zoom level other than the 375 px width and the default width was checked.
- **The video recording hides the Light/Dark button.** `test_toggle_button_selector_exists_in_the_templates_and_is_hidden_during_recording` checks that the recording script hides the button during recording. The button stays visible in the UI.
- **Unlabelled badges by colour alone are not tested for the chart.** The shape and word rules apply to the status badges. The bar chart of the run page is checked for colour contrast only.
- **Default test runs skip the slow checks.** The default `pytest` run deselects tests marked `slow`, which include the real-run and browser checks listed in section 2.

## 5. How to run the checks

The fast checks need no run and no browser:

```bash
.venv/bin/python -m pytest tests/test_story_a11y.py tests/test_story_nojs.py tests/test_story_shell.py tests/test_story_fool.py -q
```

All checks, including the ones with real runs and the browser checks, need the `screenshots` extra (Playwright) and a browser. On a Mac where Playwright's own Chromium does not run, use an installed Google Chrome:

```bash
SCREENSHOT_CHANNEL=chrome .venv/bin/python -m pytest tests/test_story_a11y.py tests/test_story_nojs.py tests/test_story_shell.py tests/test_story_fool.py tests/test_story_fragments.py tests/test_ui_home_375.py tests/test_ui_pages.py tests/test_ui_app.py tests/test_ui_error.py tests/test_ui_run_page_fixes.py tests/test_screenshots_static.py tests/test_video_tools.py -q -m "slow or not slow"
```

Without `SCREENSHOT_CHANNEL`, Playwright uses its own Chromium, which the project does not download by default (run `python -m playwright install chromium` first).

`make test-all` runs every test, including the slow ones, and `make test` runs the fast ones. The commands above select the accessibility files only. With the command above, one test of `tests/test_video_tools.py` is skipped unless the variable `CORONER_FFMPEG` names an ffmpeg binary; it is the video recording test, not an accessibility check.
