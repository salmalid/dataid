"""Reserve evaluation rows before fitting any data-dependent transformations."""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from . import config
from .context import TaskType
from .utils import infer_task_type


def reserve_holdout(ctx):
    if ctx.train_indices is not None:
        return
    df = ctx.df.copy()
    if ctx.task_type is None:
        ctx.task_type = TaskType(infer_task_type(df[ctx.target_column]))
    if ctx.target_column:
        if ctx.task_type in {TaskType.REGRESSION, TaskType.FORECASTING, TaskType.RANKING}:
            df[ctx.target_column] = pd.to_numeric(df[ctx.target_column], errors="coerce")
        df = df[df[ctx.target_column].notna()]
    df = df.drop_duplicates().reset_index(drop=True)
    if len(df) < 5:
        raise ValueError("At least five usable, distinct rows are required for training and evaluation")
    if ctx.task_type == TaskType.FORECASTING:
        df[ctx.time_column] = pd.to_datetime(df[ctx.time_column], errors="coerce", format="mixed")
        if df[ctx.time_column].isna().any():
            raise ValueError("Forecasting time column contains missing or invalid dates")
        df = df.sort_values(ctx.time_column, kind="stable").reset_index(drop=True)
        cut = max(1, int(len(df) * (1 - config.TEST_SIZE)))
        train, test = np.arange(cut), np.arange(cut, len(df))
    elif ctx.task_type == TaskType.RANKING:
        if df[ctx.group_column].isna().any():
            raise ValueError("Ranking group column contains missing values")
        splitter = GroupShuffleSplit(n_splits=1, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE)
        train, test = next(splitter.split(df, groups=df[ctx.group_column]))
    else:
        stratify = None
        if ctx.task_type == TaskType.CLASSIFICATION:
            y = df[ctx.target_column].astype(str)
            counts = y.value_counts()
            if len(counts) < 2:
                raise ValueError("Classification needs at least two target classes")
            test_size = int(np.ceil(len(df) * config.TEST_SIZE))
            if counts.min() >= 2 and len(counts) <= min(test_size, len(df) - test_size):
                stratify = y
        train, test = train_test_split(np.arange(len(df)), test_size=config.TEST_SIZE,
                                      random_state=config.RANDOM_STATE, stratify=stratify)
    ctx.df = df
    ctx.train_indices, ctx.test_indices = train, test
