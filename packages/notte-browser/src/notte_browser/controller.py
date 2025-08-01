from loguru import logger
from notte_core.actions import (
    BaseAction,
    BrowserAction,
    CaptchaSolveAction,
    CheckAction,
    ClickAction,
    CompletionAction,
    DownloadFileAction,
    FallbackFillAction,
    FillAction,
    FormFillAction,
    GoBackAction,
    GoForwardAction,
    GotoAction,
    GotoNewTabAction,
    HelpAction,
    InteractionAction,
    MultiFactorFillAction,
    PressKeyAction,
    # ReadFileAction,
    ReloadAction,
    ScrapeAction,
    ScrollDownAction,
    ScrollUpAction,
    SelectDropdownOptionAction,
    SwitchTabAction,
    UploadFileAction,
    WaitAction,
    # WriteFileAction,
)
from notte_core.browser.snapshot import BrowserSnapshot
from notte_core.common.config import config
from notte_core.credentials.types import get_str_value
from notte_core.errors.actions import ActionExecutionError
from notte_core.profiling import profiler
from notte_core.storage import BaseStorage
from notte_core.utils.code import text_contains_tabs
from notte_core.utils.platform import platform_control_key
from patchright.async_api import Locator
from typing_extensions import final

from notte_browser.captcha import CaptchaHandler
from notte_browser.dom.locate import locate_element, locate_file_upload_element, selectors_through_shadow_dom
from notte_browser.errors import (
    FailedToDownloadFileError,
    FailedToGetFileError,
    FailedToUploadFileError,
    NoStorageObjectProvidedError,
    capture_playwright_errors,
)
from notte_browser.form_filling import FormFiller
from notte_browser.window import BrowserWindow


@final
class BrowserController:
    def __init__(
        self,
        verbose: bool = False,
        storage: BaseStorage | None = None,
    ) -> None:
        self.verbose: bool = verbose
        self.storage: BaseStorage | None = storage

    async def switch_tab(self, window: BrowserWindow, tab_index: int) -> None:
        context = window.page.context
        if tab_index != -1 and (tab_index < 0 or tab_index >= len(context.pages)):
            raise ValueError(f"Tab index '{tab_index}' is out of range for context with {len(context.pages)} pages")
        tab_page = context.pages[tab_index]
        await tab_page.bring_to_front()
        window.page = tab_page
        await window.long_wait()
        if self.verbose:
            logger.info(
                f"🪦 Switched to tab {tab_index} with url: {tab_page.url} ({len(context.pages)} tabs in context)"
            )

    @profiler.profiled()
    async def execute_browser_action(self, window: BrowserWindow, action: BaseAction) -> bool:
        match action:
            case FormFillAction(value=value):
                form_filler = FormFiller(window.page)
                unpacked_values = {k: get_str_value(v) for k, v in value.items()}
                await form_filler.fill_form(unpacked_values)

            case CaptchaSolveAction(captcha_type=_):
                _ = await CaptchaHandler.handle_captchas(window, action)
            case GotoAction(url=url):
                await window.goto(url)
            case GotoNewTabAction(url=url):
                new_page = await window.page.context.new_page()
                window.page = new_page
                await window.goto(url=url)
            case SwitchTabAction(tab_index=tab_index):
                await self.switch_tab(window, tab_index)
            case WaitAction(time_ms=time_ms):
                await window.page.wait_for_timeout(time_ms)
            case GoBackAction():
                _ = await window.page.go_back()
            case GoForwardAction():
                _ = await window.page.go_forward()
            case ReloadAction():
                _ = await window.page.reload()
                await window.long_wait()
            case PressKeyAction(key=key):
                await window.page.keyboard.press(key)
            case ScrollUpAction(amount=amount):
                if amount is not None:
                    await window.page.mouse.wheel(delta_x=0, delta_y=-amount)
                else:
                    await window.page.keyboard.press("PageUp")
            case ScrollDownAction(amount=amount):
                if amount is not None:
                    await window.page.mouse.wheel(delta_x=0, delta_y=amount)
                else:
                    await window.page.keyboard.press("PageDown")

            case _:
                raise ValueError(f"Unsupported action type: {type(action)}")
        return True

    @profiler.profiled()
    async def execute_interaction_action(
        self, window: BrowserWindow, action: InteractionAction, prev_snapshot: BrowserSnapshot | None = None
    ) -> bool:
        if action.selector is None:
            raise ValueError(f"Selector is required for {action.name()}")
        press_enter = False
        if action.press_enter is not None:
            press_enter = action.press_enter
        # locate element (possibly in iframe)
        locator: Locator = await locate_element(window.page, action.selector)
        original_url = window.page.url

        action_timeout = config.timeout_action_ms

        match action:
            # Interaction actions
            case ClickAction():
                await locator.click(timeout=action_timeout)
            case FillAction(value=value):
                if text_contains_tabs(text=get_str_value(value)):
                    if self.verbose:
                        logger.info(
                            "🪦 Indentation detected in fill action: simulating clipboard copy/paste for better string formatting"
                        )
                    await locator.focus()

                    if action.clear_before_fill:
                        await window.page.keyboard.press(key=f"{platform_control_key()}+A")
                        await window.short_wait()
                        await window.page.keyboard.press(key="Backspace")
                        await window.short_wait()

                    # Use isolated clipboard variable instead of system clipboard
                    await window.page.evaluate(
                        """
                        (text) => {
                            window.__isolatedClipboard = text;
                            const dataTransfer = new DataTransfer();
                            dataTransfer.setData('text/plain', window.__isolatedClipboard);
                            document.activeElement.dispatchEvent(new ClipboardEvent('paste', {
                                clipboardData: dataTransfer,
                                bubbles: true,
                                cancelable: true
                            }));
                        }
                    """,
                        value,
                    )

                    await window.short_wait()
                else:
                    await locator.fill(get_str_value(value), timeout=action_timeout, force=action.clear_before_fill)
                    await window.short_wait()
            case MultiFactorFillAction(value=value):
                # click the locator, then fill in one number at a time
                await locator.click()

                for num in get_str_value(value):
                    await window.page.keyboard.press(key=num)
                    await window.page.wait_for_timeout(100)
            case FallbackFillAction(value=value):
                await locator.click()
                await locator.press_sequentially(get_str_value(value), delay=100)
                await window.short_wait()
            case CheckAction(value=value):
                if value:
                    await locator.check()
                else:
                    await locator.uncheck()
            case SelectDropdownOptionAction(value=value):
                # Check if it's a standard HTML select
                tag_name: str = await locator.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == "select":
                    # Handle standard HTML select
                    _ = await locator.select_option(get_str_value(value))
                else:
                    try:
                        _ = await locator.click()
                    except Exception as e:
                        raise ActionExecutionError("select_dropdown", "", reason="Invalid selector") from e
            case UploadFileAction(file_path=file_path):
                if self.storage is None or self.storage.upload_dir is None:
                    raise NoStorageObjectProvidedError(action.name())

                file_chooser_flag = False
                upload_file_path = self.storage.get_file(file_path)

                if upload_file_path is None:
                    raise FailedToGetFileError(action.id, file_path)

                if prev_snapshot is not None:
                    locator_node = prev_snapshot.dom_node.find(action.id)

                    if locator_node is not None and locator_node.attributes is not None:
                        clickable_els = ["button", "a"]

                        # To Do:
                        # try except for file chooser with set input files fallback
                        # drag and drop handler
                        # use validation within action to improve handling?
                        # change action to take list of file paths for simul multiple file upload?

                        if locator_node.attributes.tag_name in clickable_els:
                            if self.verbose:
                                logger.info("Attempting file chooser detection")
                            async with window.page.expect_file_chooser() as fc:
                                await locator.click()
                            file_chooser = await fc.value
                            await file_chooser.set_files(upload_file_path)
                            file_chooser_flag = True
                        else:
                            new_locator_node = None

                            try:
                                new_locator_node = locate_file_upload_element(locator_node)
                            except Exception as e:
                                logger.info(f"Unknown error in locate_file_upload_element: {e}")

                            if self.verbose:
                                logger.info("Tried to locate file upload input")

                            if new_locator_node is not None and new_locator_node.id != locator_node.id:
                                if self.verbose and new_locator_node.attributes is not None:
                                    logger.info(
                                        f"Found input element! {new_locator_node.attributes.tag_name}, {new_locator_node.attributes.id_name if new_locator_node.attributes.id_name is not None else None}, {new_locator_node.type}"
                                    )
                                selectors = new_locator_node.computed_attributes.selectors

                                if selectors is not None:
                                    if selectors.in_shadow_root:
                                        if self.verbose:
                                            logger.info(
                                                f"🔍 Resolving shadow root selectors for {new_locator_node.id} ({new_locator_node.text})"
                                            )
                                        selectors = selectors_through_shadow_dom(new_locator_node)

                                    locator = await locate_element(window.page, selectors)

                if not file_chooser_flag:
                    try:
                        if self.verbose:
                            logger.info("Trying to set files")
                        await locator.set_input_files(files=[upload_file_path])
                    except Exception as e:
                        logger.info("Error setting files")
                        logger.info(f"Error: {e}")
                        raise FailedToUploadFileError(
                            action_id=action.id,
                            file_path=file_path,
                            error=e,
                        )
            case DownloadFileAction():
                if self.storage is None or self.storage.download_dir is None:
                    raise NoStorageObjectProvidedError(action.name())

                async with window.page.expect_download() as dw:
                    await locator.click()
                download = await dw.value
                file_path = f"{self.storage.download_dir}{download.suggested_filename}"
                await download.save_as(file_path)
                res = self.storage.set_file(file_path)

                if not res:
                    raise FailedToDownloadFileError()

            case _:
                raise ValueError(f"Unsupported action type: {type(action)}")
        if press_enter:
            if self.verbose:
                logger.info(f"🪦 Pressing enter for action {action.id}")
                await window.short_wait()
            await window.page.keyboard.press("Enter")
        if original_url != window.page.url:
            if self.verbose:
                logger.info(f"🪦 Page navigation detected for action {action.id} waiting for networkidle")
            await window.long_wait()

        return True

    @profiler.profiled()
    @capture_playwright_errors()
    async def execute(
        self, window: BrowserWindow, action: BaseAction, prev_snapshot: BrowserSnapshot | None = None
    ) -> bool:
        context = window.page.context
        num_pages = len(context.pages)
        retval = True
        match action:
            case InteractionAction():
                retval = await self.execute_interaction_action(window, action, prev_snapshot)
            case CompletionAction(success=success, answer=answer):
                if self.verbose:
                    logger.info(
                        f"Completion action: status={'success' if success else 'failure'} with answer = {answer}"
                    )
            case ScrapeAction():
                if self.verbose:
                    logger.info("Scrape action should not be executed inside the controller")
                pass
            case HelpAction():
                if self.verbose:
                    logger.info("Help action should not be executed inside the controller")
                pass
            case BrowserAction():
                retval = await self.execute_browser_action(window, action)
            case _:
                raise ValueError(f"Unsupported action type: {type(action)}")
        # add short wait before we check for new tabs to make sure that
        # the page has time to be created
        await window.short_wait()
        if len(context.pages) != num_pages:
            if self.verbose:
                logger.info(f"🪦 Action {action.id} resulted in a new tab, switched to it...")
            await self.switch_tab(window, -1)
        return retval
