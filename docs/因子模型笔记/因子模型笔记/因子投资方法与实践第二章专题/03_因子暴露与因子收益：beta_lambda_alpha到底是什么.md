# 03 因子暴露与因子收益：Beta、Lambda、Alpha 到底是什么

> 说明：本文按《因子投资方法与实践》第 2 章的方法论脉络重讲，不摘录原书大段文字。重点是把公式、维度、推导、金融含义和中低频量化实战用法讲清楚。


## 1. 本节解决什么问题

因子模型里最容易混的是：

- 因子值。
- 因子暴露。
- 因子收益。
- 因子溢价。
- Alpha。

这一节专门把它们拆开。

## 2. 一个公式看全局

$$
R_{it}^e
=
\alpha_i
+
\beta_i'\lambda_t
+
\varepsilon_{it}
$$

展开为：

$$
R_{it}^e
=
\alpha_i
+
\sum_{k=1}^{K}\beta_{ik}\lambda_{kt}
+
\varepsilon_{it}
$$

你可以把它翻译成一句话：

**股票收益 = 模型解释不了的平均收益 + 对各因子的暴露 × 各因子本期收益 + 个股噪声。**

## 3. 因子暴露 Beta

$\beta_{ik}$ 表示资产 $i$ 对因子 $k$ 的敏感度。

如果是风险模型：

- 市场 Beta 高，说明市场涨跌对它影响大。
- 价值暴露高，说明它更像价值股。
- 动量暴露高，说明它更像近期强势股。

若对每个资产有 $K$ 个暴露：

$$
\beta_i
=
\begin{bmatrix}
\beta_{i1}\\
\beta_{i2}\\
\vdots\\
\beta_{iK}
\end{bmatrix}
$$

所有资产堆起来：

$$
B
=
\begin{bmatrix}
\beta_{11} & \beta_{12} & \cdots & \beta_{1K}\\
\beta_{21} & \beta_{22} & \cdots & \beta_{2K}\\
\vdots & \vdots & \ddots & \vdots\\
\beta_{N1} & \beta_{N2} & \cdots & \beta_{NK}
\end{bmatrix}
$$

维度：

$$
B:N\times K
$$

## 4. 因子收益 Lambda

$\lambda_{kt}$ 是第 $k$ 个因子在 $t$ 期的实现收益。

当期所有因子收益：

$$
\lambda_t
=
\begin{bmatrix}
\lambda_{1t}\\
\lambda_{2t}\\
\vdots\\
\lambda_{Kt}
\end{bmatrix}
$$

维度：

$$
\lambda_t:K\times 1
$$

因子收益可以来自两种方式：

- 排序法构造多空组合收益。
- 横截面回归估计纯因子收益。

## 5. Alpha

$\alpha_i$ 是模型解释不了的平均收益。

时间序列回归中：

$$
R_{it}^e
=
\alpha_i
+
\beta_i'f_t
+
\varepsilon_{it}
$$

如果：

$$
\alpha_i=0
$$

说明模型能解释资产 $i$ 的平均收益。

如果：

$$
\alpha_i>0
$$

且显著，则说明资产 $i$ 或组合 $i$ 可能有模型无法解释的异常收益。

## 6. 推导：组合因子暴露为什么是 $B'w$

组合收益：

$$
R_{p,t}^e
=
w'R_t^e
$$

横截面因子模型：

$$
R_t^e
=
\alpha
+
B\lambda_t
+
\varepsilon_t
$$

代入：

$$
R_{p,t}^e
=
w'\alpha
+
w'B\lambda_t
+
w'\varepsilon_t
$$

注意：

$$
w'B\lambda_t
=
(B'w)'\lambda_t
$$

所以定义组合因子暴露：

$$
b_p
=
B'w
$$

对第 $k$ 个因子：

$$
b_{p,k}
=
\sum_{i=1}^{N}w_i\beta_{ik}
$$

金融含义：

**组合对某个因子的暴露，就是组合里每只股票对该因子暴露的加权平均。**

## 7. 因子值和因子暴露的关系

在中低频选股中，很多因子暴露来自公司特征。

例如原始 BM：

$$
BM_{i,t}
=
\frac{Book_{i,t}}{Market_{i,t}}
$$

通常要经过：

1. 去极值。
2. 缺失处理。
3. 标准化。
4. 行业、市值中性化。

最后得到模型中的暴露：

$$
\beta_{i,value,t}
\quad \text{或} \quad
x_{i,value,t}
$$

所以：

**原始因子值不是天然等于可回归的因子暴露，中间需要清洗。**

## 8. 常见误解

误解一：Beta 是收益。

不对。Beta 是暴露，是属性，不是收益。

误解二：Lambda 是因子值。

不对。Lambda 是因子收益或风险溢价，是市场对暴露支付的回报。

误解三：Alpha 就是残差。

不对。Alpha 是平均意义上的未解释收益；残差是每期的随机未解释部分。

## 9. 一页速查

单资产模型：

$$
R_{it}^e
=
\alpha_i
+
\beta_i'\lambda_t
+
\varepsilon_{it}
$$

横截面模型：

$$
R_t^e
=
\alpha
+
B\lambda_t
+
\varepsilon_t
$$

组合暴露：

$$
b_p=B'w
$$

第 $k$ 个组合暴露：

$$
b_{p,k}=\sum_{i=1}^{N}w_i\beta_{ik}
$$

## 10. 练习题

1. 用自己的话解释 Beta、Lambda、Alpha。
2. 为什么组合因子暴露是单个资产暴露的加权平均？
3. 如果一个组合的市场暴露为 1.2，价值暴露为 -0.3，如何解释？
4. 为什么中低频因子值通常要先标准化再回归？
