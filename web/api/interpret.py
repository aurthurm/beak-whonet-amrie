"""Interpretation REST endpoints."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from nicegui import app

from amrie.config import read_configuration
from amrie.constants import Delimiters
from amrie.io_library import interpret_isolates, load_input_file
from web.helpers import (
    build_full_test_codes,
    generate_output_str,
    interpret_for_display,
    make_single_tab_config,
)
from web.models.requests import SingleInterpretRequest
from web.models.responses import SingleInterpretResponse, SingleInterpretResult


def _run_single_interpret(req: SingleInterpretRequest) -> SingleInterpretResponse:
    config = make_single_tab_config(
        guideline_year=req.guideline_year,
        include_comments=req.include_comments,
        restrict_breakpoint_types=req.restrict_breakpoint_types,
        breakpoint_types=req.breakpoint_types,
        restrict_sites=req.restrict_sites,
        sites_of_infection=req.sites_of_infection,
    )
    full_codes = build_full_test_codes(
        req.guidelines,
        req.whonet_abx_code,
        req.test_method,
        req.potency,
    )
    results: list[SingleInterpretResult] = []
    for code in full_codes:
        interpretation = interpret_for_display(config, req.organism_code, code, req.measurement)
        results.append(SingleInterpretResult(whonet_test=code, interpretation=interpretation))
    return SingleInterpretResponse(results=results)


@app.post('/api/interpret/single')
async def api_interpret_single(req: SingleInterpretRequest) -> SingleInterpretResponse:
    return await asyncio.to_thread(_run_single_interpret, req)


@app.post('/api/interpret/file')
async def api_interpret_file(
    data_file: UploadFile = File(...),
    config_file: UploadFile = File(...),
    delimiter: str = Form('|'),
    guideline_year: int = Form(...),
) -> Response:
    try:
        delim = Delimiters.parse_file_delimiter_token(delimiter)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data_bytes = await data_file.read()
    config_bytes = await config_file.read()

    def _run() -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / 'input.txt'
            config_path = Path(tmpdir) / 'config.json'
            data_path.write_bytes(data_bytes)
            config_path.write_bytes(config_bytes)
            columns, rows = load_input_file(str(data_path), delim)
            config = read_configuration(str(config_path))
            results = interpret_isolates(config, columns, rows, guideline_year=guideline_year)
            return generate_output_str(config, columns, results)

    output = await asyncio.to_thread(_run)
    return Response(
        content=output,
        media_type='text/tab-separated-values',
        headers={'Content-Disposition': 'attachment; filename=interpretations.txt'},
    )
