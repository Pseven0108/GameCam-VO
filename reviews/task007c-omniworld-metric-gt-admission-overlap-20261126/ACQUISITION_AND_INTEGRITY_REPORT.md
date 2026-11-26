# 最小获取与完整性边界

只对3个UID、各3对RGB/Depth取样，共18张原始PNG。相机/split/FPS/Caption复用
已有3个Others归档，不新下载完整Others。先核验归档整体SHA与清单一致，再只读目标成员。

6个RGB/depth归档使用固定revision的HTTP Range前缀，均206且Content-Range总长与源清单相等。
每流上限32MiB、总上限256MiB；实际读取18,759,680压缩字节（17.89MiB）。
找到本流3个精确成员后立即关闭，未读取完整归档；没有重试、替代成员或后续扩样。

每张PNG：完整成员字节数、逐chunk CRC、Pillow verify、完整像素解码、SHA256、dtype/尺寸均检查。
不把TAR头校验或CDN的opaque ETag当作独立SHA认证。
**前缀传输无法核验整归档LFS SHA或整个gzip CRC**；收据明确记为false。
每个完整成员有本地hash及CRC，只能据此描述本次获取完整性，不能宣称整包SHA通过。

取得的原始RGB/Depth、camera、Caption、split信息保存在本地raw_inputs，保持原字节；
公开评审只含逐项身份、检查结果和缩小的派生审查图，不发布原始数据集文件。
GT尺度来源阻断明确后未继续网络取样，后续均为既有9对的CPU验证与报告。
