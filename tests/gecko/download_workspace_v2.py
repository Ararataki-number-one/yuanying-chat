"""Real taps through the current download UI, then original native label reads."""
import json
import struct
import time
import uuid

from download_workspace_contract_v2 import PACKAGE, bounds, control, folder_dialog, nodes, verify_download_workspace


def capture(adb_scene, dump, screenshot, source, invocation, shots, stem, record):
    # This supplementary interaction has its own bounded budget. The original
    # 35-second initial scene readiness and its screenshots remain unchanged.
    deadline = time.monotonic() + 35
    evidence = dict(schema=2, sourceCommit=source, invocationNonce=invocation,
                    status='in_progress', actualAndroidExecution=True, events=[])

    def adb(*parts):
        return adb_scene(deadline, *parts)

    def event(kind, **details):
        evidence['events'].append(dict(sequence=len(evidence['events']) + 1, kind=kind,
                                       atMs=time.monotonic_ns() // 1000000, **details))

    def read_until(predicate):
        while time.monotonic() < deadline:
            xml = dump(deadline=deadline)
            try:
                predicate(xml)
                return xml
            except (AssertionError, KeyError):
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(.2, remaining))
        raise TimeoutError('Current download interaction did not reach its required UI within 35 seconds')

    def tap(xml, target, **query):
        rectangle = bounds(control(xml, record, **query))
        point = [(rectangle[0] + rectangle[2]) // 2, (rectangle[1] + rectangle[3]) // 2]
        adb('shell', 'input', 'tap', *map(str, point))
        event('tap', target=target, bounds=rectangle, point=point)

    def image(suffix):
        if time.monotonic() >= deadline:
            raise TimeoutError('Download interaction deadline expired before screenshot')
        raw = screenshot(deadline)
        assert raw.startswith(b'\x89PNG\r\n\x1a\n')
        assert list(struct.unpack('>II', raw[16:24])) == record['actualPixels']
        name = stem + suffix + '.png'
        (shots / name).write_bytes(raw)
        return name

    def reveal(description=None, text=None, stage='reveal-tools'):
        for count in range(9):
            xml = dump(deadline=deadline)
            scrolls = [node for node in nodes(xml) if node.attrib.get('class') == 'android.widget.ScrollView'
                       and node.attrib.get('package') == PACKAGE]
            assert len(scrolls) == 1, 'Expected the actual download workspace ScrollView'
            area = bounds(scrolls[0])
            try:
                item = control(xml, record, description=description, text=text)
                rectangle = bounds(item)
                # Keep both edges inside the actual scroll viewport, so a
                # partially exposed label cannot satisfy native Layout checks.
                if rectangle[1] > area[1] and rectangle[3] < area[3]:
                    return xml
            except (AssertionError, KeyError):
                pass
            if count == 8:
                break
            left, top, right, bottom = area
            x = (left + right) // 2
            low, high = top + (bottom - top) * 4 // 5, top + (bottom - top) // 5
            start, end = ([x, high], [x, low]) if stage == 'reveal-tools' else ([x, low], [x, high])
            adb('shell', 'input', 'swipe', *map(str, start + end), '350')
            event('swipe', stage=stage, **{'from': start, 'to': end}, durationMs=350)
        raise AssertionError(('Download control not fully visible after actual bounded scrolling', description, text))

    try:
        header = read_until(lambda xml: control(xml, record, description='保存位置', text=''))
        assert not any(node.attrib.get('text') == '保存位置' for node in nodes(header)), 'Default tools unexpectedly expanded'
        evidence['headerXml'] = header
        tap(header, '保存位置', description='保存位置', text='')
        dialog = read_until(lambda xml: folder_dialog(xml, record))
        evidence['dialogXml'] = dialog
        evidence['dialogXmlFile'] = stem + '-location-dialog.xml'
        (shots / evidence['dialogXmlFile']).write_text(dialog)
        evidence['dialogImage'] = image('-location-dialog')
        adb('shell', 'input', 'keyevent', '4'); event('back', keyCode=4)
        evidence['returnedXml'] = read_until(lambda xml: control(xml, record, description='保存位置', text=''))
        tools = reveal(description='展开下载工具', text='')
        evidence['beforeToolsXml'] = tools
        tap(tools, '展开下载工具', description='展开下载工具', text='')
        expanded = reveal(text='保存位置', stage='reveal-label')
        evidence['toolsXml'] = expanded
        nonce = uuid.uuid4().hex
        adb('shell', 'am', 'start', '-W', '--activity-single-top', '-n', PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity',
            '--es', 'visualObserveAction', 'download-workspace-location', '--es', 'visualObserveNonce', nonce,
            '--es', 'visualParentNonce', invocation, '--es', 'visualSourceCommit', source)
        payloads = []
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-s', 'PocketDownloadLabel:I', '*:S')
            payloads = [line[line.index('{'):] for line in raw.splitlines() if '{' in line
                        and json.loads(line[line.index('{'):]).get('nonce') == nonce]
            if payloads:
                break
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(.2, remaining))
        assert len(payloads) == 1, ('Missing or duplicate native expanded download label observation', payloads)
        record.update(downloadLocationNonce=nonce, downloadLocationRaw=payloads[0])
        (shots / (stem + '-download-location.json')).write_text(payloads[0] + '\n')
        # The exact original native observer and original v1 reader still check
        # all four drawn characters, no ellipsis, full bounds and 48-dp touches.
        from ui_visual_contract import verify_download_location
        verify_download_location(record, source)
        evidence['measuredXml'] = dump(deadline=deadline)
        evidence['toolsXmlFile'] = stem + '-expanded-tools.xml'
        (shots / evidence['toolsXmlFile']).write_text(evidence['measuredXml'])
        evidence['toolsImage'] = image('-expanded-tools')
        evidence.update(status='passed', actualAndroidTaps=2, actualAndroidBack=1,
                        actualAndroidSwipes=sum(item['kind'] == 'swipe' for item in evidence['events']))
        record.update(downloadWorkspaceContract=2, downloadWorkspace=evidence)
        verify_download_workspace(record, source)
    except Exception as error:
        evidence.update(status='failed', error=type(error).__name__)
        raise
    finally:
        (shots / (stem + '-download-workspace-v2.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
