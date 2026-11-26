# RGB与像素坐标合同

1. 原图Pillow convert RGB；除255一次，float32 CHW。
2. 按官方255000像素上限选14倍数，1920×1080恰好变成672×378（254016pixels），无裁剪、无填充、宽高比不变。
3. 模型内部ImageNet归一化；适配器不重复。
4. 仅最后时刻概率在CPU bilinear align_corners=False恢复原尺寸，再做M>0.4。
5. 半像素映射矩阵：[[0.35,0,-0.325],[0,0.35,-0.325],[0,0,1]]。输入、每帧mapping与源SHA完整保存。

CPU合成RGB红/绿/蓝与官方load_images_as_tensor逐位一致。错误uint8/BGR送入通用tensor helper会产生差别，说明应验证域；这不等于断言官方所有调用路径有错误。
独立float64插值复算及64张Mask检查见statistics/CPU_ARTIFACT_VALIDATION.json；边界的双线性软化是已记录后处理，不是原生全分辨率分割。
