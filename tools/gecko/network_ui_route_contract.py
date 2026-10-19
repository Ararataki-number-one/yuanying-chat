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
