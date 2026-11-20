"""The tour of the editor and its lessons (gpu-studio standard §5a): the tour starts by itself once,
every step of the tour and of every lesson finds its part on the demo, every text is there in both
languages, a lesson done by clicking to the end, and the "?" of a step offers its lesson."""

from __future__ import annotations

from playwright.sync_api import expect
import pytest

ONLY_WITH_DATA = {
    "reference/result",
    "audition/results",
    "audition/apply",
    "synthesize/timing",
    "queue/poweroff",
    "jobs/stop",
    "jobs/history",
}
# every step of a lesson, with what it frames: its own part, or (None) only the fallback part
STEPS_JS = """async () => {
  const { LESSONS } = await import('/static/lessons.js');
  const editor = document.querySelector('pvc-editor');
  return LESSONS.map((lesson) => ({ key: lesson.key, steps: lesson.steps.map((step) => ({
    key: step.key, click: step.advance === 'click', fallback: Boolean(step.fallback) })) }));
}"""
FOUND_JS = """async ([lesson, index]) => {
  const { LESSONS } = await import('/static/lessons.js');
  const { findTarget } = await import('/static/tour.js');
  const editor = document.querySelector('pvc-editor');
  const step = LESSONS.find((item) => item.key === lesson).steps[index];
  const targets = typeof step.targets === 'function' ? step.targets(editor) : step.targets;
  return targets.filter((target) => findTarget(editor, target)).length;
}"""
TEXTS_JS = """async () => {
  const { LESSONS } = await import('/static/lessons.js');
  const { TOUR_STEPS } = await import('/static/tour.js');
  const { STRINGS } = await import('/static/i18n.js');
  const keys = [];
  for (const step of TOUR_STEPS) {
    keys.push(`tour_${step.key}_title`, `tour_${step.key}_text`);
    if (step.where) keys.push(`tour_${step.key}_where`);
  }
  for (const lesson of LESSONS) {
    keys.push(`lesson_${lesson.key}_name`, `lesson_${lesson.key}_about`);
    if (lesson.needs) keys.push(`lessons_needs_${lesson.needs}`);
    for (const step of lesson.steps) {
      keys.push(`lesson_${lesson.key}_${step.key}_title`, `lesson_${lesson.key}_${step.key}_text`);
    }
  }
  keys.push(...['start', 'more', 'once'].map((group) => `lessons_${group}`));
  const missing = (language) => keys.filter((key) => !STRINGS[language][key]);
  return Object.fromEntries(Object.keys(STRINGS).map((language) => [language, missing(language)]));
}"""


def start_lesson(page, key):
    page.evaluate(f"document.querySelector('pvc-editor')._startLesson('{key}')")
    expect(page.locator("[data-tour-bubble]")).to_be_visible()


def click_frame(page):
    """A click in the middle of the frame: on the framed part, through the blocked rest."""
    page.wait_for_timeout(450)  # the frame moves to its part in 0.25 s and follows it every 0.4 s
    box = page.locator("[data-tour-frame]").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_the_tour_starts_by_itself_once_and_from_the_gear(browser, demo):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.add_init_script("localStorage.getItem('pvc-lang') || localStorage.setItem('pvc-lang', 'pl')")
    page = context.new_page()
    page.goto(f"{demo[0]}/")
    page.wait_for_function("window.editorReady === true")
    bubble = page.locator("[data-tour-bubble]")
    expect(bubble).to_have_attribute("data-tour-bubble", "welcome")
    expect(bubble).to_contain_text("Witaj w edytorze głosów")
    seen = []
    while True:
        key = bubble.get_attribute("data-tour-bubble")
        seen.append(key)
        if key != "welcome":
            expect(page.locator(f"[data-tour-frame='{key}']")).to_be_visible()  # its part is framed
        if page.locator("[data-tour-next]").inner_text() == "Gotowe":
            page.locator("[data-tour-next]").click()
            break
        page.locator("[data-tour-next]").click()
    assert seen[:4] == ["welcome", "tree", "new_voice", "middle"] and "help" in seen, seen
    expect(bubble).to_have_count(0)
    page.reload()
    page.wait_for_function("window.editorReady === true")
    page.wait_for_timeout(300)
    expect(bubble).to_have_count(0)  # seen: not again
    page.locator("[data-editor-settings]").click()
    page.locator("[data-gear-tour]").click()
    expect(bubble).to_have_attribute("data-tour-bubble", "welcome")
    page.keyboard.press("Escape")
    expect(bubble).to_have_count(0)
    context.close()


def test_every_text_of_the_tour_and_the_lessons_is_in_both_languages(page):
    page.open()
    missing = page.evaluate(TEXTS_JS)
    assert missing == {"en": [], "pl": []}, missing


def test_every_step_of_every_lesson_finds_its_part_on_the_demo(page):
    page.open("voice/kasia")
    lessons = page.evaluate(STEPS_JS)
    assert len(lessons) >= 18
    only_fallback = []
    for lesson in lessons:
        if lesson["key"].startswith("new_"):
            continue  # they make a voice: gone through in their own test below
        start_lesson(page, lesson["key"])
        for index, step in enumerate(lesson["steps"]):
            bubble = page.locator("[data-tour-bubble]")
            expect(bubble).to_have_attribute("data-tour-bubble", step["key"])
            frame = page.locator(f"[data-tour-frame='{step['key']}']")
            expect(frame, f"{lesson['key']}/{step['key']}").to_be_visible()
            page.wait_for_timeout(150)
            if not page.evaluate(FOUND_JS, [lesson["key"], index]):
                assert step["fallback"], f"{lesson['key']}/{step['key']}: nothing to frame"
                only_fallback.append(f"{lesson['key']}/{step['key']}")
            if step["click"]:
                click_frame(page)
            else:
                page.locator("[data-tour-next]").click()
        expect(page.locator("[data-tour-bubble]")).to_have_count(0)
        page.keyboard.press("Escape")  # what a lesson opened (the ⚙ box) closes
    # only a part that comes with what the demo has not got is framed by its place: the results of a job not
    # run, a running job, finished jobs, the switch of Home Assistant (the demo has no connection)
    assert set(only_fallback) <= ONLY_WITH_DATA, sorted(set(only_fallback) - ONLY_WITH_DATA)


@pytest.mark.parametrize("language", ["pl", "en"])
def test_the_lessons_list_marks_the_ones_gone_through(page, language):
    page.open()
    page.evaluate(f"localStorage.setItem('pvc-lang', '{language}')")
    page.reload()
    page.wait_for_function("window.editorReady === true")
    page.locator("[data-editor-settings]").click()
    page.locator("[data-gear-lessons]").click()
    expect(page.locator("[data-lessons-group]")).to_have_count(3)
    if language == "pl":  # "2 kroki", "5 kroków"
        expect(page.locator("[data-lesson='elevenlabs']")).to_contain_text("2 kroki")
        expect(page.locator("[data-lesson='train']")).to_contain_text("7 kroków")
    page.locator("[data-lesson='look']").click()
    expect(page.locator("[data-tour-bubble='gear']")).to_be_visible()
    click_frame(page)  # the ⚙ box opens and the lesson goes on
    for key in ("theme", "language", "more"):
        expect(page.locator(f"[data-tour-bubble='{key}']")).to_be_visible()
        page.locator("[data-tour-next]").click()
    page.locator("[data-editor-settings]").click()
    page.locator("[data-gear-lessons]").click()
    expect(page.locator("[data-lesson='look'] [data-lesson-done]")).to_be_visible()
    expect(page.locator("[data-lesson='train'] [data-lesson-done]")).to_have_count(0)


def test_a_new_voice_made_in_its_lesson(page, demo):
    root = demo[1]
    page.open()
    start_lesson(page, "new_import")
    click_frame(page)  # + New voice
    expect(page.locator("[data-tour-bubble='way']")).to_be_visible()
    click_frame(page)  # I already have recordings
    expect(page.locator("[data-tour-bubble='name']")).to_be_visible()
    page.locator("pvc-new-voice [data-new-name]").fill("lekcja")  # the framed fields can be typed in
    page.locator("[data-tour-next]").click()
    expect(page.locator("[data-tour-bubble='create']")).to_be_visible()
    click_frame(page)  # Create
    expect(page.locator("[data-tour-bubble='steps']")).to_be_visible()
    assert (root / "voices" / "lekcja" / "voice.yaml").is_file()
    expect(page.locator("[data-node='voice/lekcja/import']")).to_be_visible()
    page.locator("[data-tour-next]").click()
    expect(page.locator("[data-tour-bubble]")).to_have_count(0)
    assert "new_import" in page.evaluate("localStorage.getItem('pvc-studio-lessons')")


def test_the_help_of_a_step_offers_its_lesson(page):
    page.open("voice/kasia/train")
    page.locator("[data-step-help] [data-help-button]").first.click()
    offer = page.locator("[data-help-lesson='train']")
    expect(offer).to_contain_text("Trening głosu")
    offer.click()
    expect(page.locator("[data-tour-count]")).to_contain_text("Trening głosu · 1 z")
    expect(page.locator("[data-tour-frame='node']")).to_be_visible()


# the only parts a lesson waits to be clicked: quick and undoable; a training, the clips, an export or the
# machine's power are shown and pressed by the person
CLICK_TARGETS = {
    "[data-new-voice-button]",
    "pvc-new-voice >>> [data-workflow='clone']",
    "pvc-new-voice >>> [data-workflow='import']",
    "pvc-new-voice >>> [data-new-create]",
    "[data-editor-settings]",
}
CLICKS_JS = """async () => {
  const { LESSONS } = await import('/static/lessons.js');
  const editor = document.querySelector('pvc-editor');
  return LESSONS.flatMap((lesson) => lesson.steps.filter((step) => step.advance === 'click')
    .flatMap((step) => (typeof step.targets === 'function' ? step.targets(editor) : step.targets)));
}"""


def test_a_lesson_waits_only_for_quick_clicks(page):
    page.open()
    clicked = set(page.evaluate(CLICKS_JS))
    assert clicked <= CLICK_TARGETS, sorted(clicked - CLICK_TARGETS)


def test_next_on_a_step_that_waits_does_the_click(page):
    page.open()
    start_lesson(page, "look")
    page.locator("[data-tour-next]").click()  # instead of ⚙ itself
    expect(page.locator("[data-gear-box]")).to_be_visible()
    expect(page.locator("[data-tour-bubble='theme']")).to_be_visible()


def test_keys_in_a_field_belong_to_the_field_and_the_bubble_leaves_the_frame_free(page):
    page.open()
    start_lesson(page, "new_clone")
    page.locator("[data-tour-next]").click()
    expect(page.locator("[data-tour-bubble='way']")).to_be_visible()
    page.locator("[data-tour-next]").click()
    expect(page.locator("[data-tour-bubble='name']")).to_be_visible()
    name = page.locator("pvc-new-voice [data-new-name]")
    name.fill("ola")
    name.press("ArrowLeft")  # moves the cursor, not the lesson
    page.wait_for_timeout(500)
    expect(page.locator("[data-tour-bubble='name']")).to_be_visible()
    frame = page.locator("[data-tour-frame]").bounding_box()
    bubble = page.locator("[data-tour-bubble]").bounding_box()
    apart = (
        bubble["x"] >= frame["x"] + frame["width"]
        or bubble["x"] + bubble["width"] <= frame["x"]
        or bubble["y"] >= frame["y"] + frame["height"]
        or bubble["y"] + bubble["height"] <= frame["y"]
    )
    assert apart, (frame, bubble)
    name.press("Enter")  # submits the form of the field (a voice made), the lesson stays where it was
    expect(page.locator("[data-tour-bubble='name']")).to_be_visible()
