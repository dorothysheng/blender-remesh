import sys
import os
import glob
import bpy
import bmesh
from mathutils import Vector
import math

def parse_arguments():
    """Parse command line arguments - simple version"""
    TARGET_REDUCTION = 0.5  # Default 50%
    
    # Look for --reduction or -r in all arguments
    for i, arg in enumerate(sys.argv):
        if arg in ['--reduction', '-r']:
            if i + 1 < len(sys.argv):
                try:
                    TARGET_REDUCTION = float(sys.argv[i + 1])
                    print(f"📊 从命令行读取减少比例: {TARGET_REDUCTION}")
                except ValueError:
                    print(f"⚠️ 无效的减少比例值: {sys.argv[i + 1]}, 使用默认值 0.5")
    
    return TARGET_REDUCTION

def setup_scene_for_screenshot(obj):
    """设置场景用于截图"""
    # 清除默认立方体等对象，但保留我们的目标对象
    objects_to_delete = [o for o in bpy.context.scene.objects if o != obj]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects_to_delete:
        o.select_set(True)
    if objects_to_delete:
        bpy.ops.object.delete(use_global=False)
    
    # 确保只有我们的对象被选中
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # 计算对象的边界盒和尺寸
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_coords = Vector([min(corner[i] for corner in bbox_corners) for i in range(3)])
    max_coords = Vector([max(corner[i] for corner in bbox_corners) for i in range(3)])
    
    # 计算对象的中心和最大尺寸
    center = (min_coords + max_coords) / 2
    dimensions = max_coords - min_coords
    max_dimension = max(dimensions)
    
    # 根据对象大小计算相机距离
    camera_distance = max_dimension * 1.5  # 相机距离是最大尺寸的1.5倍
    camera_height = max_dimension * 0.8    # 相机高度
    
    # 设置相机位置（45度角度，俯视）
    camera_location = Vector([
        center.x + camera_distance * 0.7,  # X偏移
        center.y - camera_distance * 0.7,  # Y偏移  
        center.z + camera_height            # Z高度
    ])
    
    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    
    # 设置为场景的活动相机
    bpy.context.scene.camera = camera
    
    # 相机看向对象中心
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = obj
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'
    
    # 调整相机的视野角度，确保对象完全可见
    camera.data.lens = 35  # 35mm镜头，视野较宽
    
    # 添加光源，位置也根据对象大小调整
    light_location = Vector([
        center.x + camera_distance * 0.5,
        center.y + camera_distance * 0.5,
        center.z + camera_distance * 1.2
    ])
    
    bpy.ops.object.light_add(type='SUN', location=light_location)
    light = bpy.context.object
    light.data.energy = 3
    light.data.angle = 0.2  # 较软的阴影
    
    return camera

def capture_wireframe_screenshot(obj, filepath):
    """渲染带线框风格的截图"""
    try:
        # 清空现有材质
        obj.data.materials.clear()

        # 创建新材质
        mat = bpy.data.materials.new(name="WireframeMaterial")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # 创建必要节点
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        mix_shader = nodes.new(type='ShaderNodeMixShader')
        diffuse_shader = nodes.new(type='ShaderNodeBsdfDiffuse')
        emission_shader = nodes.new(type='ShaderNodeEmission')
        wireframe_node = nodes.new(type='ShaderNodeWireframe')

        # 设置颜色
        emission_shader.inputs['Color'].default_value = (0.2, 0.8, 1.0, 1.0)  # 蓝色线条
        diffuse_shader.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)  # 黑色底色

        # 连接节点
        links.new(wireframe_node.outputs['Fac'], mix_shader.inputs['Fac'])
        links.new(diffuse_shader.outputs['BSDF'], mix_shader.inputs[1])
        links.new(emission_shader.outputs['Emission'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], output_node.inputs['Surface'])

        # 应用材质
        obj.data.materials.append(mat)

        # 设置渲染参数
        scene = bpy.context.scene
        # 安全设置渲染引擎（兼容新旧版本）
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except TypeError:
            scene.render.engine = 'BLENDER_EEVEE'
        scene.render.image_settings.file_format = 'PNG'
        scene.render.resolution_x = 800
        scene.render.resolution_y = 600
        scene.render.film_transparent = True

        # 渲染
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)

        print(f"  ✓ 截图保存: {os.path.basename(filepath)}")
        return True

    except Exception as e:
        print(f"  ❌ 截图失败: {e}")
        return False


def import_obj_file(filepath):
    print(f"  Importing: {os.path.basename(filepath)}")
    try:
        bpy.ops.wm.obj_import(filepath=filepath)
        print("  ✓ Import succeeded")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False

def export_obj_file(filepath):
    try:
        bpy.ops.wm.obj_export(filepath=filepath)
        print(f"  ✓ Exported: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"  ✗ Export failed: {e}")
        return False

def is_valid_obj(o):
    try:
        _ = o.name
        return o.type == 'MESH' and len(o.data.polygons) > 0
    except (ReferenceError, AttributeError):
        return False

def analyze_mesh_quality(obj):
    """分析网格质量，判断最适合的减面方法"""
    if not is_valid_obj(obj):
        return "unknown"
    
    mesh = obj.data
    face_count = len(mesh.polygons)
    vert_count = len(mesh.vertices)
    
    # 计算拓扑特征
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    
    # 分析面的几何特征
    quad_faces = sum(1 for f in bm.faces if len(f.verts) == 4)
    tri_faces = sum(1 for f in bm.faces if len(f.verts) == 3)
    
    # 分析边长分布
    edge_lengths = [e.calc_length() for e in bm.edges]
    avg_edge_length = sum(edge_lengths) / len(edge_lengths) if edge_lengths else 0
    
    bm.free()
    
    quad_ratio = quad_faces / face_count if face_count > 0 else 0
    vert_face_ratio = vert_count / face_count if face_count > 0 else 0
    
    print(f"  📊 网格分析:")
    print(f"    - 面数: {face_count}, 顶点: {vert_count}")
    print(f"    - 四边形比例: {quad_ratio:.2f}")
    print(f"    - 顶点/面比例: {vert_face_ratio:.2f}")
    print(f"    - 平均边长: {avg_edge_length:.4f}")
    
    # 判断网格类型
    if quad_ratio > 0.7:
        return "structured"  # 结构化网格，适合quadric decimation
    elif vert_face_ratio > 0.8:
        return "dense"       # 密集网格，适合aggressive decimation
    else:
        return "organic"     # 复杂几何，需要保形处理

def try_quadric_decimate(obj, target_reduction, preserve_sharp=True):
    """使用quadric decimation，保持形状质量"""
    try:
        print(f"    🔧 应用Quadric Edge Collapse (减少 {target_reduction*100:.0f}%)")
        
        # 确保对象处于正确状态
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 清除现有修改器
        obj.modifiers.clear()
        
        # 检查是否有足够的面数进行减面
        original_faces = len(obj.data.polygons)
        if original_faces < 4:
            print(f"    ⚠️ 面数太少({original_faces})，跳过减面")
            return False
        
        # 添加decimate修改器
        decimate_mod = obj.modifiers.new(name="QuadricDecimate", type='DECIMATE')
        decimate_mod.decimate_type = 'COLLAPSE'
        decimate_mod.ratio = max(0.1, 1 - target_reduction)  # 确保ratio不小于0.1
        decimate_mod.use_collapse_triangulate = False  # 保持四边形
        
        if preserve_sharp:
            decimate_mod.angle_limit = math.radians(15)  # 保护特征边缘
        
        # 强制更新
        bpy.context.view_layer.update()
        
        # 应用修改器
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)
        
        # 检查是否真的减少了面数
        new_faces = len(obj.data.polygons)
        if new_faces < original_faces:
            return True
        else:
            print(f"    ⚠️ 修改器未生效，面数未改变")
            return False
        
    except Exception as e:
        print(f"    ❌ Quadric decimate失败: {e}")
        return False

def try_unsubdiv_decimate(obj, iterations=2):
    """使用un-subdivide减面"""
    try:
        print(f"    🔧 应用Un-Subdivide ({iterations} 次迭代)")
        
        # 确保对象处于正确状态
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
        
        original_faces = len(obj.data.polygons)
        
        obj.modifiers.clear()
        
        decimate_mod = obj.modifiers.new(name="UnsubDiv", type='DECIMATE')
        decimate_mod.decimate_type = 'UNSUBDIV'
        decimate_mod.iterations = iterations
        
        # 强制更新
        bpy.context.view_layer.update()
        
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)
        
        # 检查是否减少了面数
        new_faces = len(obj.data.polygons)
        return new_faces < original_faces
        
    except Exception as e:
        print(f"    ❌ Un-subdivide失败: {e}")
        return False

def try_planar_decimate(obj, angle_threshold=5):
    """使用planar decimation"""
    try:
        print(f"    🔧 应用Planar Decimation (角度阈值: {angle_threshold}°)")
        
        # 确保对象处于正确状态
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
        
        original_faces = len(obj.data.polygons)
        
        obj.modifiers.clear()
        
        decimate_mod = obj.modifiers.new(name="PlanarDecimate", type='DECIMATE')
        decimate_mod.decimate_type = 'DISSOLVE'
        decimate_mod.angle_limit = math.radians(angle_threshold)
        decimate_mod.use_dissolve_boundaries = False
        
        # 强制更新
        bpy.context.view_layer.update()
        
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)
        
        # 检查是否减少了面数
        new_faces = len(obj.data.polygons)
        return new_faces < original_faces
        
    except Exception as e:
        print(f"    ❌ Planar decimate失败: {e}")
        return False

def apply_subdivision_surface_then_decimate(obj, target_reduction):
    """先细分再减面，获得更优拓扑结构"""
    try:
        print(f"    🔧 应用SubSurf + Decimate策略")
        
        original_faces = len(obj.data.polygons)
        
        # 添加subdivision surface
        subsurf_mod = obj.modifiers.new(name="SubSurf", type='SUBSURF')
        subsurf_mod.levels = 1  # 只细分一级
        subsurf_mod.render_levels = 1
        
        # 应用subdivision
        bpy.ops.object.modifier_apply(modifier=subsurf_mod.name)
        
        subdivided_faces = len(obj.data.polygons)
        print(f"      细分后面数: {subdivided_faces}")
        
        # 计算新的减面比例
        adjusted_reduction = 1 - (original_faces * (1 - target_reduction)) / subdivided_faces
        adjusted_reduction = max(0.1, min(0.9, adjusted_reduction))  # 限制范围
        
        print(f"      调整减面比例: {adjusted_reduction:.2f}")
        
        # 应用quadric decimation
        return try_quadric_decimate(obj, adjusted_reduction, preserve_sharp=True)
        
    except Exception as e:
        print(f"    ❌ SubSurf策略失败: {e}")
        return False

def apply_smart_smooth(obj):
    """智能表面平滑优化"""
    try:
        # 进入编辑模式
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 选择所有
        bpy.ops.mesh.select_all(action='SELECT')
        
        # 重新计算法线
        bpy.ops.mesh.normals_make_consistent(inside=False)
        
        # 回到对象模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 应用平滑着色
        bpy.ops.object.shade_smooth()
        
        # 添加edge split修改器来保护特征边缘
        edge_split = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        edge_split.split_angle = math.radians(30)  # 30度特征角分割
        bpy.ops.object.modifier_apply(modifier=edge_split.name)
        
        return True
        
    except Exception as e:
        print(f"    ❌ 平滑处理失败: {e}")
        bpy.ops.object.mode_set(mode='OBJECT')
        return False

def intelligent_mesh_reduction(obj, target_reduction=0.5):
    """智能网格减面，根据网格类型选择最佳策略"""
    if not is_valid_obj(obj):
        print("⚠️ 无效对象")
        return False
    
    original_faces = len(obj.data.polygons)
    print(f"\n🔄 开始智能减面: {obj.name}")
    print(f"原始面数: {original_faces}")
    
    if original_faces < 100:
        print("  面数太少，跳过处理")
        return True
    
    # 分析网格质量
    mesh_type = analyze_mesh_quality(obj)
    success = False
    
    target_faces = int(original_faces * (1 - target_reduction))
    
    # 根据网格类型选择策略
    if mesh_type == "structured":
        print("\n  📐 检测到结构化网格，使用拓扑保持策略")
        
        strategies = [
            ("Conservative Quadric", lambda: try_quadric_decimate(obj, target_reduction * 0.7, True)),
            ("Un-Subdivide", lambda: try_unsubdiv_decimate(obj, 2)),
            ("Standard Quadric", lambda: try_quadric_decimate(obj, target_reduction, True)),
            ("Planar Dissolve", lambda: try_planar_decimate(obj, 5)),
        ]
        
    elif mesh_type == "dense":
        print("\n  🔍 检测到密集网格，使用渐进优化策略")
        
        strategies = [
            ("SubSurf + Decimate", lambda: apply_subdivision_surface_then_decimate(obj, target_reduction)),
            ("Progressive Quadric", lambda: try_quadric_decimate(obj, target_reduction * 0.8, True)),
            ("Un-Subdivide", lambda: try_unsubdiv_decimate(obj, 3)),
            ("Aggressive Quadric", lambda: try_quadric_decimate(obj, target_reduction, False)),
        ]
        
    else:  # organic
        print("\n  🌿 检测到复杂曲面，使用形状保持策略")
        
        strategies = [
            ("Quality Quadric", lambda: try_quadric_decimate(obj, target_reduction * 0.6, True)),
            ("SubSurf + Decimate", lambda: apply_subdivision_surface_then_decimate(obj, target_reduction)),
            ("Planar + Quadric", lambda: try_planar_decimate(obj, 3) and try_quadric_decimate(obj, target_reduction * 0.5, True)),
            ("Standard Quadric", lambda: try_quadric_decimate(obj, target_reduction, True)),
        ]
    
    # 尝试各种策略
    for i, (strategy_name, strategy_func) in enumerate(strategies, 1):
        print(f"\n  🎯 策略 {i}: {strategy_name}")
        
        faces_before = len(obj.data.polygons)
        
        if strategy_func():
            faces_after = len(obj.data.polygons)
            reduction = (faces_before - faces_after) / faces_before * 100
            
            print(f"    结果: {faces_after} 面 (减少 {reduction:.1f}%)")
            
            # 检查是否有效果
            if faces_after < faces_before * 0.95:  # 至少减少5%
                success = True
                
                # 如果接近目标，结束尝试
                if target_faces * 0.7 <= faces_after <= target_faces * 1.3:
                    print(f"    ✅ 接近目标，停止尝试")
                    break
    
    # 应用智能平滑
    if success:
        print(f"\n  ✨ 应用后处理...")
        apply_smart_smooth(obj)
    
    # 最终统计
    final_faces = len(obj.data.polygons)
    final_reduction = (original_faces - final_faces) / original_faces * 100
    
    if final_faces < original_faces:
        print(f"  ✅ 减面成功: {original_faces} → {final_faces} 面 (减少 {final_reduction:.1f}%)")
        return True
    else:
        print(f"  ❌ 减面失败: 面数未改变")
        return False

def process_obj_file(filepath, target_reduction=0.5):
    """处理单个OBJ文件"""
    print(f"\n{'='*80}")
    print(f"📄 处理文件: {os.path.basename(filepath)}")
    print(f"🎯 目标: 减少 {target_reduction*100:.0f}% 面数")
    print(f"📸 截图模式: 启用")
    print(f"{'='*80}")
    
    # 清空场景
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # 导入文件
    if not import_obj_file(filepath):
        return False
    
    # 获取导入的对象
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not mesh_objects:
        print("❌ 没有导入任何网格对象")
        return False
    
    print(f"📦 导入了 {len(mesh_objects)} 个对象")
    
    # 如果有多个对象，合并它们
    if len(mesh_objects) > 1:
        print("🔗 合并多个对象...")
        bpy.ops.object.select_all(action='DESELECT')
        for obj in mesh_objects:
            obj.select_set(True)
        
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.object.join()
        main_obj = bpy.context.view_layer.objects.active
    else:
        main_obj = mesh_objects[0]
    
    # 记录原始面数
    original_faces = len(main_obj.data.polygons)
    base_filename = os.path.splitext(os.path.basename(filepath))[0]
    
    # 设置输出目录
    script_dir = os.path.dirname(__file__)
    output_dir = os.path.join(script_dir, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 拍摄原始截图
    print("\n📸 拍摄原始模型截图...")
    camera = setup_scene_for_screenshot(main_obj)
    before_path = os.path.join(output_dir, f"{base_filename}_before.png")
    capture_wireframe_screenshot(main_obj, before_path)
    
    # 执行智能减面
    success = intelligent_mesh_reduction(main_obj, target_reduction)
    
    if success:
        final_faces = len(main_obj.data.polygons)
        actual_reduction = (original_faces - final_faces) / original_faces * 100
        
        print(f"\n🏁 处理完成:")
        print(f"   📊 原始面数: {original_faces:,}")
        print(f"   📊 最终面数: {final_faces:,}")
        print(f"   📊 实际减少: {actual_reduction:.1f}%")
        
        # 拍摄处理后截图
        print("\n📸 拍摄处理后截图...")
        after_path = os.path.join(output_dir, f"{base_filename}_after.png")
        capture_wireframe_screenshot(main_obj, after_path)
        
        # 检查质量
        if actual_reduction >= target_reduction * 100 * 0.7:  # 至少达到目标的70%
            print(f"   ✅ 达到预期效果!")
        elif actual_reduction > 10:
            print(f"   ⚠️ 有一定改善")
        else:
            print(f"   ❌ 改善有限")
        
        return True
    else:
        print("❌ 处理失败")
        return False

def main():
    # Parse command line arguments - simple way
    TARGET_REDUCTION = parse_arguments()
    
    # Validate reduction value
    if not 0.0 <= TARGET_REDUCTION <= 1.0:
        print(f"❌ Error: Reduction must be between 0.0 and 1.0, got {TARGET_REDUCTION}")
        return
    
    print("🚀 开始Blender智能减面处理 v2.0")
    print("🎯 智能拓扑优化系统")
    print(f"📊 目标减少: {TARGET_REDUCTION*100:.0f}%")
    print("📸 自动截图: 启用")
    
    # 设置路径
    script_dir = os.path.dirname(__file__)
    input_dir = os.path.join(script_dir, "input")
    output_dir = os.path.join(script_dir, "output")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 查找OBJ文件
    obj_files = glob.glob(os.path.join(input_dir, "*.obj"))
    if not obj_files:
        print(f"❌ 在 {input_dir} 中没有找到OBJ文件")
        return
    
    print(f"📁 发现 {len(obj_files)} 个OBJ文件")
    
    successful_files = 0
    
    for i, filepath in enumerate(obj_files, 1):
        try:
            success = process_obj_file(filepath, TARGET_REDUCTION)
            
            if success:
                # 导出文件
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                output_filename = f"{base_name}_remeshed.obj"
                output_path = os.path.join(output_dir, output_filename)
                
                if export_obj_file(output_path):
                    successful_files += 1
                    print(f"✅ 文件 {i}/{len(obj_files)} 处理成功")
                else:
                    print(f"❌ 文件 {i}/{len(obj_files)} 导出失败")
            else:
                print(f"❌ 文件 {i}/{len(obj_files)} 处理失败")
                
        except Exception as e:
            print(f"❌ 文件 {i}/{len(obj_files)} 发生错误: {e}")
    
    print(f"\n🎉 处理完成!")
    print(f"📊 成功处理: {successful_files}/{len(obj_files)} 个文件")
    print(f"📁 输出目录: {output_dir}")

if __name__ == "__main__":
    main()