class TestToolCallsCollection:
    CODEX_STREAM = chr(10).join([
        '{"type":"turn.started"}',
        '{"type":"item.completed","item":{"id":"i1","type":"reasoning","text":"think"}}',
        '{"type":"item.completed","item":{"id":"i2","type":"tool_call","name":"read_file","input":{"path":"a.py"}}}',
        '{"type":"item.completed","item":{"id":"i3","type":"mcp_tool_call","tool_name":"mcp__teamchat__list_tasks","input":{}}}',
        '{"type":"item.completed","item":{"id":"i4","type":"command_execution","command":"grep -n foo a.py","exit_code":0}}',
        '{"type":"item.completed","item":{"id":"i5","type":"agent_message","text":"done"}}',
    ])

    def test_codex_stream_collects_tool_calls(self):
        from engine.codex_events import collect_codex_tool_calls
        calls = collect_codex_tool_calls(self.CODEX_STREAM)
        names = [c[chr(110)+'ame'] for c in calls]
        assert 'read_file' in names
        assert 'mcp__teamchat__list_tasks' in names
        assert any('grep -n foo a.py' in n for n in names)
        assert all(isinstance(c['input'], dict) for c in calls)

    def test_cursor_stream_collects_tool_use(self):
        from engine.runner import collect_cursor_tool_calls
        stream = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__teamchat__create_task","input":{"title":"t"}},{"type":"text","text":"hi"}]}}'
        calls = collect_cursor_tool_calls(stream)
        assert calls == [{chr(110)+'ame': 'mcp__teamchat__create_task', 'input': {'title': 't'}}]

    def test_summarize_truncates_long_input(self):
        from engine.runner import _summarize_tool_input
        out = _summarize_tool_input({'data': 'x' * 500})
        assert 'preview' in out and len(out['preview']) == 300
        assert _summarize_tool_input({'a': 1}) == {'a': 1}

    def test_collected_tool_calls_persist_to_store(self, tmp_path):
        from engine.config import Config
        from engine.codex_events import collect_codex_tool_calls
        from engine.session_store import SessionStore as TeamChatSessionStore
        from engine.store import AgentCallStore
        config = Config(repo_owner='t', repo_name='t', repo_url='https://t/t', project_root=tmp_path)
        ss = TeamChatSessionStore(config); ss.init()
        store = AgentCallStore(config); store.init()
        calls = collect_codex_tool_calls(self.CODEX_STREAM)
        store.log(agent_name='coco咪', prompt='p', output='done', exit_code=0,
                  duration_ms=1, task_type='scheduled_task', tag='prod',
                  token_usage={'input_tokens': 1, 'output_tokens': 1},
                  tool_calls=calls,
                  started_at='2026-08-03T00:00:00+00:00', finished_at='2026-08-03T00:00:30+00:00')
        row = store.get_by_id(1)
        assert len(row.tool_calls) == 3
        assert row.tool_calls[0][chr(110)+'ame'] == 'read_file'
        store.close(); ss.close()
