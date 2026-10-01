# B/NZ实验（Judge r55反馈后）

父版本r41。r55支持r54完整入口MISS，具体拒绝条件仍未知。本轮不用r54的N余数或新macro整除门槛，使用原r30的Case12已知范围。

假设：一次性B预打包增加全局读写及barrier，但消除每个M分片重复ND→NZ转换。保留A的ND2NZ、原plan、AM128BN256、K1=256/K0=64及r30预取。总GM→L1逻辑B字节不减少；不把预打包称为B加载复用。

冻结验证：沿用164组CPU FP64参考。32组screen及96组holdout使用原先固定划分。筛选计时包含整个融合kernel的PackB、同步和compute，不能仅计打包后的Cube。screen若收益混合，门槛必须先由screen确定、再用holdout验证；无稳定子域则不提交Judge。

PackB用两块32KiB UB，输入和输出均为raw16字节搬运，不对BF16做half算术。所有AIV参与pack结束barrier；AIC等待组内两AIV发布PACK_TO_CUBE，再读packed GM。flag0/2与ring4..7以及SyncAll保留flag分离。UB总量在190KiB以内；GPU/NPU实测前仍需验证API与索引。

## 第二轮：r57

r56筛选整体中位回退6.83%，最差回退20.68%；N%128==64且TA=true有部分收益，N%128==0回退明显，故不直接提交。

r57只改变packed GM布局为[Nmacro,Kstage,N16,K256,16]，打包成本仍计入完整kernel。希望用单次连续GM→L1搬运替换r56的跨K跨度分段搬运。沿用原32组screen，尚未查看r57结果，不预设会有收益。若整齐N子域仍失败，不把局部非整齐N收益泛化到Case12。
