"""DOM Tree utilities"""


def print_tree(node, indent=0):
    """DOM 트리를 콘솔에 출력"""
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


def tree_to_list(tree, result_list):
    """DOM 트리를 flat list로 변환"""
    result_list.append(tree)
    for child in tree.children:
        tree_to_list(child, result_list)
    return result_list
