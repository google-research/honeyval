"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


def intersection_over_union(set1: set[int], set2: set[int]) -> float:
    """
    Calculates the intersection over union score of two sets containing integers.

    Args:
        set1 (set): The first set.
        set2 (set): The second set.

    Returns:
        Intersection over union (IoU) score.
    """
    if len(set1) + len(set2) < 1:
        iou = 1.0
    else:
        iou = len(set1.intersection(set2)) / len(set1.union(set2))
    return iou


def f1(tp: int | float, fp: int | float, tn: int | float, fn: int | float) -> float:
    """
    Calculates the F1 score.

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        F1 score.
    """
    if tp == 0:
        return 0.0
    else:
        return 2 * tp / (2 * tp + fp + fn)


def accuracy(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the accuracy.

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Accuracy.
    """
    total = tp + fp + tn + fn
    if total == 0:
        return 0.0
    else:
        return (tp + tn) / total


def precision(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the precision.

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Precision.
    """
    if tp + fp == 0:
        return 0.0
    else:
        return tp / (tp + fp)


def recall(tp: int | float, fp: int | float, tn: int | float, fn: int | float) -> float:
    """
    Calculates the recall (also known as sensitivity or true positive rate).

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Recall.
    """
    if tp + fn == 0:
        return 0.0
    else:
        return tp / (tp + fn)


def specificity(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the specificity (also known as true negative rate).

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Specificity.
    """
    if tn + fp == 0:
        return 0.0
    else:
        return tn / (tn + fp)


def false_positive_rate(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the false positive rate.

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        False positive rate.
    """
    if fp + tn == 0:
        return 0.0
    else:
        return fp / (fp + tn)


def false_negative_rate(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the false negative rate.

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        False negative rate.
    """
    if fn + tp == 0:
        return 0.0
    else:
        return fn / (fn + tp)


def negative_predictive_value(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the negative predictive value (NPV).

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Negative predictive value.
    """
    if tn + fn == 0:
        return 0.0
    else:
        return tn / (tn + fn)


def false_discovery_rate(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the false discovery rate (FDR).

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        False discovery rate.
    """
    if fp + tp == 0:
        return 0.0
    else:
        return fp / (fp + tp)


def balanced_accuracy(
    tp: int | float, fp: int | float, tn: int | float, fn: int | float
) -> float:
    """
    Calculates the balanced accuracy (average of sensitivity and specificity).

    Args:
        tp (int or float): True positives.
        fp (int or float): False positives.
        tn (int or float): True negatives.
        fn (int or float): False negatives.

    Returns:
        Balanced accuracy.
    """
    sens = recall(tp, fp, tn, fn)
    spec = specificity(tp, fp, tn, fn)
    return (sens + spec) / 2.0
