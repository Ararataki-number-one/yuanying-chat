"""Read actual accessible route stages within one named environment card."""
import re


def visible_route(tree, environment, entrance, fixed_exit):
    parents = {child: parent for parent in tree.iter() for child in parent}
    for title in tree.iter('node'):
        if title.attrib.get('text') != environment:
            continue
        card = parents.get(title)
        while card is not None:
            # The nearest ancestor with this card's edit action is its boundary;
            # another environment elsewhere on the screen cannot satisfy it.
            if any(node.attrib.get('text') == '编辑网络' and
                   node.attrib.get('class') == 'android.widget.Button'
                   for node in card.iter('node')):
                texts = [node for node in card.iter('node') if node.attrib.get('text')]
                labels = [node.attrib['text'] for node in texts]
                for key, expected in (('入口', entrance), ('固定出口', fixed_exit), ('目的地', 'ChatGPT')):
                    if labels.count(key) != 1:
                        return False
                    index = labels.index(key) + 1
                    if index >= len(texts) or labels[index] != expected:
                        return False
                    value = texts[index]
                    bounds = list(map(int, re.findall(r'\d+', value.attrib.get('bounds', ''))))
                    if (len(bounds) != 4 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]
                            or value.attrib.get('clickable') != 'false'):
                        return False
                return True
            card = parents.get(card)
    return False


def reveal_modal_action(read, swipe, title, text, package, record=None, max_scrolls=6):
    """Reveal an actual action with bounded swipes inside the named modal only.

    This never invokes the target action or substitutes a native callback for a
    touch. The caller still taps once and verifies the original data assertions.
    """
    for attempt in range(max_scrolls + 1):
        tree = read()
        headings = [n for n in tree.iter('node') if n.attrib.get('content-desc') == title]
        assert len(headings) == 1, 'Expected the named modal before revealing an action'
        actions = [n for n in tree.iter('node') if n.attrib.get('text') == text
                   and n.attrib.get('class') == 'android.widget.Button'
                   and n.attrib.get('package') == package]
        assert len(actions) <= 1, 'Ambiguous modal action'
        if actions:
            rect = list(map(int, re.findall(r'\d+', actions[0].attrib.get('bounds', ''))))
            assert len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1]
            assert actions[0].attrib.get('enabled') == 'true', 'Modal action is disabled'
            assert actions[0].attrib.get('clickable') == 'true', 'Modal action is not clickable'
            return tree
        assert attempt < max_scrolls, 'Actual modal swipes did not reveal action: ' + text
        containers = [n for n in tree.iter('node') if n.attrib.get('class') == 'android.widget.ScrollView'
                      and n.attrib.get('package') == package and n.attrib.get('scrollable') == 'true']
        assert len(containers) == 1, 'Expected one actual scrollable modal body'
        rect = list(map(int, re.findall(r'\d+', containers[0].attrib.get('bounds', ''))))
        assert len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1]
        left, top, right, bottom = rect
        x = (left + right) // 2
        start, end = top + (bottom - top) * 4 // 5, top + (bottom - top) // 5
        assert left < x < right and top < end < start < bottom
        if record is not None:
            record(attempt=attempt + 1, title=title, actionText=text, container=containers[0].attrib,
                   command=['shell', 'input', 'swipe', str(x), str(start), str(x), str(end), '600'])
        swipe(x, start, x, end)
    raise AssertionError('Unreachable modal action state')
