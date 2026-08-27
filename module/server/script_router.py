# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import Response, StreamingResponse
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from module.config.utils import convert_to_underscore
from module.config.config_model import ConfigModel
from module.config.weekly_schedule import WeeklySchedule

from module.logger import logger
from module.server.api_logger import ApiLoggingRoute, log_ws_event
from module.server.config_manager import (
    ConfigAlreadyExistsError,
    ConfigJsonError,
    ConfigManager,
    ConfigNameError,
    ConfigNotFoundError,
    ConfigTaskError,
    ConfigValidationError,
)
from module.server.main_manager import mm
from module.server.script_process import ScriptProcess, ScriptState

from tasks.Component.config_base import TimeDelta


script_app = APIRouter(route_class=ApiLoggingRoute)


class WeeklyScheduleEntryRequest(BaseModel):
    task: str
    weekday: int = Field(ge=1, le=7)
    time: str


class WeeklyScheduleRequest(BaseModel):
    enabled: bool = True
    catch_up_missed: bool = False
    turtle_mode: bool | None = None
    turtle_keep_tasks: list[str] | None = None
    entries: list[WeeklyScheduleEntryRequest] = Field(default_factory=list)


def _weekly_schedule_tasks(config):
    tasks = []
    for key in config.model.dict().keys():
        task_object = getattr(config.model, key, None)
        scheduler = getattr(task_object, 'scheduler', None)
        if scheduler is None:
            continue
        try:
            task_name = ConfigModel.type(key)
        except (KeyError, IndexError):
            continue
        tasks.append({
            'name': task_name,
            'enabled': bool(scheduler.enable),
            'next_run': str(scheduler.next_run),
        })
    return tasks


def _weekly_schedule_response(script_name: str):
    config = mm.config_cache(script_name)
    schedule = WeeklySchedule(script_name)
    data = schedule.load()
    tasks = _weekly_schedule_tasks(config)
    now = datetime.now().replace(microsecond=0)
    week_start = now.date() - timedelta(days=now.isoweekday() - 1)
    planned_keys = {
        convert_to_underscore(entry['task'])
        for entry in data['entries']
    }
    next_runs = {
        task['name']: task['next_run']
        for task in tasks
        if task['next_run']
    }
    return {
        **data,
        'entries': [
            {
                **entry,
                'scheduled_at': str(schedule.current_week_datetime(entry, now)),
            }
            for entry in data['entries']
        ],
        'tasks': tasks,
        'planned_tasks': [
            task['name'] for task in tasks
            if convert_to_underscore(task['name']) in planned_keys
        ],
        'unplanned_tasks': [
            task['name'] for task in tasks
            if convert_to_underscore(task['name']) not in planned_keys
        ],
        'next_runs': next_runs,
        'server_now': str(now),
        'current_week_start': str(week_start),
        'today_weekday': now.isoweekday(),
    }


async def _broadcast_schedule(script_name: str, config):
    if script_name not in mm.script_process:
        return
    config.get_next()
    await mm.script_process[script_name].broadcast_state({
        'schedule': config.get_schedule_data(),
    })


@script_app.get('/test')
async def script_test():
    return 'success'

@script_app.get('/script_menu')
async def script_menu():
    return mm.config_cache('template').gui_menu_list
# ----------------------------------   配置文件管理   ----------------------------------
@script_app.get('/config_list')
async def config_list():
    return mm.all_script_files()

@script_app.post('/config_copy')
async def config_copy(file: str, template: str = 'template'):
    mm.copy(file, template)
    return mm.all_script_files()

@script_app.get('/config_new_name')
async def config_new_name():
    return mm.generate_script_name()

@script_app.get('/config_all')
async def config_all():
    return mm.all_json_file()


@script_app.post('/config/import')
async def config_import(name: str = Form(...), file: UploadFile = File(...)):
    """
    导入脚本配置文件，上传文件名不会作为落盘名称。
    """
    try:
        raw = await file.read()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as e:
            raise ConfigJsonError(f'Config file must be UTF-8 JSON: {e}') from e
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigJsonError(f'Config JSON parse failed: {e}') from e

        config_name = mm.import_config(name, data)
        mm.add_script_file(config_name)
        return {"name": config_name, "file": f"{config_name}.json"}
    except ConfigAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "fields": e.fields},
        )
    except (ConfigNameError, ConfigJsonError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.get('/config/export')
async def config_export(name: str):
    """
    导出脱敏后的脚本配置文件。
    """
    try:
        config_name, data = mm.load_config_for_export(name)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConfigJsonError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redacted = ConfigManager.redact_config(data)
    content = json.dumps(redacted, indent=2, ensure_ascii=False, sort_keys=False, default=str)
    filename = f"{config_name}.json"
    quoted_filename = quote(filename, safe='')
    fallback_filename = "config.json"
    return Response(
        content=content,
        media_type='application/json; charset=utf-8',
        headers={
            'Content-Disposition': f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{quoted_filename}",
            'Cache-Control': 'no-store',
        },
    )


@script_app.post('/config/task/import')
async def config_task_import(
    config_name: str = Form(...),
    task_name: str = Form(...),
    json_text: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    """
    导入单个任务配置 JSON，内容必须是 {"task_key": {...}}。
    """
    try:
        file_content = await file.read() if file is not None else None
        data = mm.parse_task_json_source(json_text=json_text, file_content=file_content)
        config_name, task_key = mm.import_task_config(config_name, task_name, data)
        return {
            "config_name": config_name,
            "task_name": task_key,
            "file": f"{config_name}.json",
            "updated": True,
        }
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "fields": e.fields},
        )
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.get('/config/task/export')
async def config_task_export(config_name: str, task_name: str):
    """
    导出脱敏后的单个任务配置 JSON 文件。
    """
    try:
        config_name, task_key, data = mm.load_task_for_export(config_name, task_name)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
    filename = f"{config_name}-{task_key}.json"
    quoted_filename = quote(filename, safe='')
    fallback_filename = "task.json"
    return Response(
        content=content,
        media_type='application/json; charset=utf-8',
        headers={
            'Content-Disposition': f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{quoted_filename}",
            'Cache-Control': 'no-store',
        },
    )


@script_app.get('/config/task/copy-json')
async def config_task_copy_json(config_name: str, task_name: str):
    """
    复制单个任务配置 JSON，返回未脱敏普通 JSON。
    """
    try:
        _, _, data = mm.load_task_for_transfer(config_name, task_name)
        return data
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.put('/config')
async def config_rename(old_name: str = '', new_name: str = ''):
    """
    update config name
    :param old_name: old config name
    :param new_name: new config name
    :return: True or False
    """
    if old_name == new_name or new_name == '':
        return False
    if old_name in mm.script_process:
        if mm.script_process[old_name].state != ScriptState.INACTIVE:
            mm.script_process[old_name].stop()
        del mm.script_process[old_name]
    if not mm.rename(old_name, new_name):
        raise HTTPException(status_code=400, detail='Rename failed')
    return True


@script_app.delete('/config')
async def config_delete(name: str = ''):
    """
    delete config file
    :param name: config name
    :return: True or False
    """
    if name == '' or name == 'template':
        raise HTTPException(status_code=400, detail='Delete failed')
    if name in mm.script_process:
        if mm.script_process[name].state != ScriptState.INACTIVE:
            mm.script_process[name].stop()
        del mm.script_process[name]
    if not mm.delete(name):
        raise HTTPException(status_code=400, detail='Delete failed')
    return True


@script_app.put('/config/task/copy')
async def task_copy(task_name: str, dest_config_name: str, source_config_name: str):
    if dest_config_name not in mm.script_process or source_config_name not in mm.script_process:
        return False
    source_task = getattr(mm.config_cache(source_config_name).model, convert_to_underscore(task_name), None)
    if source_task is None:
        return False
    return mm.config_cache(dest_config_name).model.copy_script_task(task_name, source_task)


@script_app.put('/config/task/group/copy')
async def task_group_copy(task_name: str, group_name: str, dest_config_name: str, source_config_name: str):
    if dest_config_name not in mm.script_process or source_config_name not in mm.script_process:
        return False
    source_task = getattr(mm.config_cache(source_config_name).model, convert_to_underscore(task_name), None)
    if source_task is None:
        return False
    return mm.config_cache(dest_config_name).model.copy_task_group(task_name, group_name, source_task)


# ---------------------------------   脚本实例管理   ----------------------------------
@script_app.get('/{script_name}/start')
async def script_start(script_name: str):
    if script_name not in mm.script_process:
        mm.script_process[script_name] = ScriptProcess(script_name)
    mm.script_process[script_name].start()
    return

@script_app.get('/{script_name}/stop')
async def script_stop(script_name: str):
    if script_name not in mm.script_process:
        logger.warning(f'[{script_name}] script process does not exist')
        return
    mm.script_process[script_name].stop()
    return


@script_app.get('/{script_name}/weekly_schedule')
async def get_weekly_schedule(script_name: str):
    if script_name not in mm.all_script_files():
        raise HTTPException(status_code=404, detail='Config not found')
    return _weekly_schedule_response(script_name)


@script_app.put('/{script_name}/weekly_schedule')
async def put_weekly_schedule(script_name: str, payload: WeeklyScheduleRequest):
    if script_name not in mm.all_script_files():
        raise HTTPException(status_code=404, detail='Config not found')
    config = mm.config_cache(script_name)
    available_tasks = {
        convert_to_underscore(task['name']): task['name']
        for task in _weekly_schedule_tasks(config)
    }
    entries = []
    for item in payload.entries:
        task_key = convert_to_underscore(item.task)
        if task_key not in available_tasks:
            raise HTTPException(status_code=400, detail=f'Unknown scheduled task: {item.task}')
        entries.append({
            'task': available_tasks[task_key],
            'weekday': item.weekday,
            'time': item.time,
        })
    schedule = WeeklySchedule(script_name)
    previous = schedule.load()
    turtle_keep_tasks = None
    if payload.turtle_keep_tasks is not None:
        turtle_keep_tasks = []
        for task in payload.turtle_keep_tasks:
            task_key = convert_to_underscore(task)
            if task_key not in available_tasks:
                raise HTTPException(status_code=400, detail=f'Unknown turtle task: {task}')
            turtle_keep_tasks.append(available_tasks[task_key])
    effective_turtle_mode = (
        previous['turtle_mode']
        if payload.turtle_mode is None
        else payload.turtle_mode
    )
    effective_turtle_tasks = (
        previous['turtle_keep_tasks']
        if turtle_keep_tasks is None
        else turtle_keep_tasks
    )
    if effective_turtle_mode and not effective_turtle_tasks:
        raise HTTPException(status_code=400, detail='Turtle mode requires at least one retained task')
    try:
        schedule.save(
            payload.enabled,
            entries,
            payload.catch_up_missed,
            payload.turtle_mode,
            turtle_keep_tasks,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _weekly_schedule_response(script_name)


@script_app.post('/{script_name}/weekly_schedule/apply')
async def apply_weekly_schedule(script_name: str):
    if script_name not in mm.all_script_files():
        raise HTTPException(status_code=404, detail='Config not found')
    config = mm.config_cache(script_name)
    result = config.apply_weekly_schedule_today(force=True)
    if result['applied'] or result['disabled'] or result['restored']:
        await _broadcast_schedule(script_name, config)
    response = _weekly_schedule_response(script_name)
    response['applied_tasks'] = sorted(result['applied'])
    response['skipped_tasks'] = sorted(result['skipped'])
    response['disabled_tasks'] = sorted(result['disabled'])
    response['restored_tasks'] = sorted(result['restored'])
    return response

@script_app.get('/{script_name}/{task}/args')
async def script_task(script_name: str, task: str):
    return mm.config_cache(script_name).model.script_task(task)

@script_app.put('/{script_name}/{task}/{group}/{argument}/value')
async def script_task(script_name: str, task: str, group: str, argument: str, types: str, value):
    try:
        match types:
            case 'integer':
                value = int(value)
            case 'number':
                value = float(value)
            case 'boolean':
                if isinstance(value, str):
                    logger.warning(f'[{script_name}] script argument {argument} value is string, try to convert to bool')
                    if value.lower() in ['true', '1']:
                        value = True
                    elif value.lower() in ['false', '0']:
                        value = False
                value = bool(value)
            case 'string':
                pass
            case 'date_time':
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            case 'time_delta':
                # strptime 是个好东西，但是不能解析00的天数
                day = int(value[1])
                date_time = datetime.strptime(value[3:], '%H:%M:%S')
                value = TimeDelta(days=day, hours=date_time.hour, minutes=date_time.minute, seconds=date_time.second)
            case 'time':
                value = datetime.strptime(value, '%H:%M:%S').time()
            case _: pass
    except Exception as e:
        # 类型不正确
        raise HTTPException(status_code=400, detail=f'Argument type error: {e}')
    return mm.config_cache(script_name).model.script_set_arg(task, group, argument, value)


@script_app.put('/{script_name}/{task}/sync_next_run')
async def sync_next_run(script_name: str, task: str, target_dt: str):
    if script_name not in mm.script_process:
        return False
    config = mm.config_cache(script_name)
    target = datetime.strptime(target_dt, '%Y-%m-%d %H:%M:%S') if target_dt else None
    config.task_delay(task=task, success=True, target=target)
    script_process = mm.script_process[script_name]
    config.get_next()
    await script_process.broadcast_state({"schedule": config.get_schedule_data()})
    return True


# --------------------------------------  SSE  --------------------------------------
@script_app.get('/{script_name}/state')
async def script_task_state(script_name: str):
    async def state_generate_events():
        while True:
            # 生成 SSE 事件数据
            event_data = "data: Hello, SSE!\n\n"
            yield event_data

            # 模拟异步操作，可以替换为您的实际处理逻辑
            await asyncio.sleep(1)

    response = StreamingResponse(state_generate_events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    return response

@script_app.get('/{script_name}/log')
async def script_task_log(script_name: str):
    async def log_generate_events():
        while True:
            # 生成 SSE 事件数据
            event_data = "data: log\n"
            yield event_data

            # 模拟异步操作，可以替换为您的实际处理逻辑
            await asyncio.sleep(1)

    response = StreamingResponse(log_generate_events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    return response

# -------------------------------------- websocket --------------------------------------

@script_app.websocket("/ws/{script_name}")
async def websocket_endpoint(websocket: WebSocket, script_name: str):
    if script_name not in mm.script_process:
        mm.script_process[script_name] = ScriptProcess(script_name)
    script_process = mm.script_process[script_name]
    await script_process.connect(websocket)
    log_ws_event(f"ws[{script_name}] connected")

    try:
        await script_process.send_json(websocket, {"state": script_process.state})
        log_ws_event(f"ws[{script_name}] connect state: {script_process.state}")
        config = mm.config_cache(script_name)
        config.get_next()
        schedule_data = config.get_schedule_data()
        await script_process.send_json(websocket, {"schedule": schedule_data})
        log_ws_event(f"ws[{script_name}] connect response: {schedule_data}")
        while True:
            # 初次进入，广播state schedule
            data = await websocket.receive_text()
            log_ws_event(f"ws[{script_name}] msg: {data}")
            if data == 'get_state':
                await script_process.broadcast_state({"state": script_process.state})
                log_ws_event(f"ws[{script_name}] response: {script_process.state}")
            elif data == 'get_schedule':
                config = mm.config_cache(script_name)
                config.get_next()
                schedule_data = config.get_schedule_data()
                await script_process.broadcast_state({"schedule": schedule_data})
                log_ws_event(f"ws[{script_name}] response: {schedule_data}")
            elif data == 'start':
                await script_process.start()
            elif data == 'stop':
                await script_process.stop()

    except WebSocketDisconnect:
        log_ws_event(f"ws[{script_name}] disconnect", level="warning")
        await script_process.disconnect(websocket)
    except Exception as e:
        log_ws_event(f"ws[{script_name}] error: {type(e).__name__}: {e}", level="error")
        logger.exception(f'[{script_name}] websocket error: {e}')
        await script_process.disconnect(websocket)
