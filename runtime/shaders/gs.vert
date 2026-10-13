#version 450
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec4 in_color;
layout(location = 2) in vec3 in_stq;
layout(location = 3) in float in_fog;
layout(location = 4) in uint in_round_uv;
layout(location = 5) in uvec2 in_clamp;

layout(location = 0) out vec4 v_color;
layout(location = 1) out vec3 v_stq;
layout(location = 2) out float v_fog;
layout(location = 3) flat out uint v_round_uv;
layout(location = 4) flat out uvec2 v_clamp;

layout(push_constant) uniform PC {
    vec2  inv_size;
    vec2  tex_size;
    uvec4 flags;
    vec4  fogcol;
    uvec4 clamp_uv;
    vec2  img_size;
    float scale;
    float point_size;
    float tex_scale;
    uint  clut_xy;
} pc;

void main() {
    v_color = in_color / 128.0;
    v_stq   = in_stq;
    v_fog   = in_fog;
    v_round_uv = in_round_uv;
    v_clamp = in_clamp;
    gl_PointSize = pc.point_size;
    gl_Position = vec4(in_pos.x * pc.inv_size.x - 1.0,
                       in_pos.y * pc.inv_size.y - 1.0,
                       in_pos.z, 1.0);
}
