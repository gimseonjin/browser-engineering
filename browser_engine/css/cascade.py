"""CSS Cascade Priority"""


def cascade_priority(rule):
    """CSS 규칙의 우선순위를 반환"""
    selector, body = rule
    return selector.priority
