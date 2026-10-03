# Notebooks 目录说明

探索式分析（EDA）在此进行。**结论性代码最终应沉淀为 `scripts/` 下的脚本**，Notebook 保留探索过程。

## 计划清单

| 文件 | 内容 | 状态 |
|------|------|------|
| `01_data_profiling.ipynb` | 数据初探：形状、类型、缺失、时间范围 | ⬜ |
| `02_eda_geography.ipynb` | 地理分布探索 | ⬜ |
| `03_eda_price.ipynb` | 价格分布与影响因素 | ⬜ |
| `04_eda_host.ipynb` | 房东结构探索 | ⬜ |

## 约定

- Notebook 提交前**务必清空输出**（体积大且暴露本地路径）
  ```bash
  jupyter nbconvert --clear-output --inplace notebooks/*.ipynb
  ```
- 图表若为最终成果，导出到 `visualizations/`
