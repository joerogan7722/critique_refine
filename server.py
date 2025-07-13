import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional

from fastmcp import Context, FastMCP

from mcp_servers.critique_refine.core.loop import CritiqueRefineLoop
from mcp_servers.critique_refine.core.model_router import initialize, ModelAPIError
from mcp_servers.critique_refine.models import CritiqueRefineResult
from mcp_servers.critique_refine.utils.config import (
    get_gemini_api_key,
    get_config,
    build_run_config,
)

logger = logging.getLogger(__name__)


class CritiqueRefineLogic:
    def __init__(self):
        self.full_config = get_config()
        gemini_api_key = get_gemini_api_key()
        if gemini_api_key:
            try:
                initialize(api_key=gemini_api_key)
            except ModelAPIError as e:
                logger.warning(f"Model API initialization failed: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found. Tool will not be operational.")


@dataclass
class AppContext:
    critique_refine_logic: CritiqueRefineLogic


@asynccontextmanager
async def lifespan(mcp: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manages the lifecycle of the critique-refine logic, initializing it once
    at startup and making it available in the application state.
    """
    yield AppContext(critique_refine_logic=CritiqueRefineLogic())


mcp = FastMCP(
    name="critique-refine-server",
    lifespan=lifespan,
)


@mcp.tool("run_critique_refine_loop")
async def run_critique_refine_loop(
    content_to_improve: str,
    strategy_name: str,
    ctx: Context,
    custom_roles: Optional[List[str]] = None,
    iterations: Optional[int] = None,
) -> CritiqueRefineResult:
    """
    Executes a full critique-refine loop on a given piece of text or code
    using a specified strategy and optional custom roles.
    """
    critique_refine_logic = ctx.request_context.lifespan_context.critique_refine_logic

    if not get_gemini_api_key():
        return CritiqueRefineResult(
            final_content="",
            run_log="",
            error="GEMINI_API_KEY environment variable not set."
        )

    logger.info(f"Starting Critique-Refine Loop with strategy: {strategy_name}")

    args_dict = {
        "strategy": strategy_name,
        "multi_critic_roles": ",".join(custom_roles) if custom_roles else None,
        "critic_role": None,
        "refiner_role": None,
        "save_improvement": False,
        "quick": False,
        "redact_logs": False,
        "debug": False,
        "dry_run": False,
        "delete_input_file": False,
    }

    run_config = build_run_config(args_dict, critique_refine_logic.full_config)

    if iterations is not None:
        run_config.max_rounds = iterations

    try:
        loop = CritiqueRefineLoop(run_config, strategy=strategy_name)
        final_output, _ = await loop.run(initial_user_prompt=content_to_improve)
        logger.info("Critique-Refine Loop Finished.")
        return CritiqueRefineResult(
            final_content=final_output,
            run_log="Critique-Refine loop completed successfully. Check logs for details."
        )
    except Exception as e:
        logger.error(f"An error occurred during critique-refine loop: {e}", exc_info=True)
        return CritiqueRefineResult(
            final_content="",
            run_log="",
            error=str(e)
        )


if __name__ == "__main__":
    # Basic logging setup for the server
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(mcp.run_stdio_async())
