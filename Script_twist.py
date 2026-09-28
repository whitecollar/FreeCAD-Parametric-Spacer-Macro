import FreeCAD as App
import FreeCADGui as Gui
import Part
import math


# ============================================================
# ОСНОВНЫЕ ПАРАМЕТРЫ
# ============================================================

height = 120.0

# Полная толщина сверху / снизу
thickness_top = 30.0
thickness_bottom = 10.0

# Максимальный поворот между передней
# и задней поверхностью
#
#  15 = по часовой/против часовой в зависимости от системы
# -15 = противоположное направление
#   0 = без скручивания
twist_angle_deg = 15.0

# Количество промежуточных сечений.
# Чем больше, тем плавнее twist.
twist_sections = 9


# ============================================================
# ПРОФИЛЬ
#
# distance = расстояние от верхней точки
# width    = полная ширина
# ============================================================

measurements = [
    (10.0, 28.0),
    (20.0, 35.0),
    (30.0, 40.0),
    (40.0, 42.0),
    (60.0, 42.0),
    (80.0, 38.0),
    (100.0, 30.0),
    (110.0, 20.0),
]


# ============================================================
# ПЛОТНОСТЬ И СГЛАЖИВАНИЕ
# ============================================================

samples_per_segment = 48

fair_passes = 8
fair_strength = 0.22


# ============================================================
# КОРРЕКЦИЯ ШИРИНЫ
# ============================================================

side_correction = 0.0

correction_start = 20.0
correction_end = 70.0

correction_ramp = 5.0


# ============================================================
# ПОДГОТОВКА ДАННЫХ
# ============================================================

stations = measurements + [
    (height, 0.0)
]

depths = [
    p[0]
    for p in stations
]

radii = [
    p[1] / 2.0
    for p in stations
]

original_width = max(
    p[1]
    for p in measurements
)


# ============================================================
# ТОЛЩИНА НА ЛЮБОЙ ВЫСОТЕ
# ============================================================

def thickness_at_distance(distance):

    return (

        thickness_top

        + (
            thickness_bottom
            - thickness_top
        )

        * distance
        / height

    )


# ============================================================
# МОНОТОННЫЕ НАКЛОНЫ
# ============================================================

def monotone_slopes(x, values):

    count = len(x)

    h = [
        x[i + 1] - x[i]
        for i in range(count - 1)
    ]

    sec = [
        (
            values[i + 1]
            - values[i]
        ) / h[i]

        for i in range(count - 1)
    ]

    slopes = [0.0] * count


    def endpoint(
        h0,
        h1,
        d0,
        d1
    ):

        result = (

            (
                (2.0 * h0 + h1)
                * d0
                - h0 * d1
            )

            / (h0 + h1)

        )

        if result * d0 <= 0.0:

            return 0.0

        if (

            d0 * d1 < 0.0

            and

            abs(result)
            > 3.0 * abs(d0)

        ):

            return 3.0 * d0

        return result


    slopes[0] = endpoint(
        h[0],
        h[1],
        sec[0],
        sec[1]
    )

    slopes[-1] = endpoint(
        h[-1],
        h[-2],
        sec[-1],
        sec[-2]
    )


    for i in range(
        1,
        count - 1
    ):

        before = sec[i - 1]
        after = sec[i]

        if before * after <= 0:

            slopes[i] = 0.0

        else:

            w1 = (
                2.0 * h[i]
                + h[i - 1]
            )

            w2 = (
                h[i]
                + 2.0 * h[i - 1]
            )

            slopes[i] = (

                (w1 + w2)

                / (
                    w1 / before
                    + w2 / after
                )

            )

    return slopes


slopes = monotone_slopes(
    depths,
    radii
)


# ============================================================
# КУБИЧЕСКИЕ СЕГМЕНТЫ ПРОФИЛЯ
# ============================================================

segments = []

first_depth = depths[0]
first_radius = radii[0]

handle_depth = (
    first_depth / 3.0
)


segments.append([

    (0.0, 0.0),

    (
        first_radius * 0.55,
        0.0
    ),

    (
        first_radius
        - slopes[0] * handle_depth,

        first_depth
        - handle_depth
    ),

    (
        first_radius,
        first_depth
    ),
])


for i in range(
    len(depths) - 1
):

    step = (
        depths[i + 1]
        - depths[i]
    )

    segments.append([

        (
            radii[i],
            depths[i]
        ),

        (
            radii[i]
            + slopes[i] * step / 3.0,

            depths[i]
            + step / 3.0
        ),

        (
            radii[i + 1]
            - slopes[i + 1]
            * step / 3.0,

            depths[i + 1]
            - step / 3.0
        ),

        (
            radii[i + 1],
            depths[i + 1]
        ),

    ])


# ============================================================
# ИСХОДНЫЕ ТОЧКИ
# ============================================================

def create_base_points():

    smooth_segments = [
        list(poles)
        for poles in segments
    ]

    # плавное нижнее окончание
    smooth_segments[-1][-2] = (
        4.0,
        height
    )


    all_segments = list(
        smooth_segments
    )


    # зеркальная половина
    for poles in reversed(
        smooth_segments
    ):

        mirrored = [

            (
                -x,
                distance
            )

            for x, distance
            in reversed(poles)

        ]

        all_segments.append(
            mirrored
        )


    points = []


    for poles in all_segments:

        for i in range(
            samples_per_segment
        ):

            t = (
                i
                / float(
                    samples_per_segment
                )
            )

            u = 1.0 - t


            weights = [

                u ** 3,

                3.0
                * u * u * t,

                3.0
                * u * t * t,

                t ** 3,

            ]


            x = sum(

                weights[j]
                * poles[j][0]

                for j in range(4)

            )


            distance = sum(

                weights[j]
                * poles[j][1]

                for j in range(4)

            )


            y = (
                height / 2.0
                - distance
            )


            points.append(

                App.Vector(
                    x,
                    y,
                    0
                )

            )


    return points


# ============================================================
# FAIRING
# ============================================================

def fair_closed_points(
    points,
    passes,
    strength
):

    pts = [

        App.Vector(
            p.x,
            p.y,
            0
        )

        for p in points
    ]


    for _ in range(passes):

        old = pts
        new = []

        count = len(old)


        for i in range(count):

            before = old[
                (i - 1) % count
            ]

            current = old[i]

            after = old[
                (i + 1) % count
            ]


            avg_x = (
                before.x
                + after.x
            ) / 2.0


            avg_y = (
                before.y
                + after.y
            ) / 2.0


            new.append(

                App.Vector(

                    current.x
                    * (1.0 - strength)
                    + avg_x * strength,

                    current.y
                    * (1.0 - strength)
                    + avg_y * strength,

                    0

                )

            )


        pts = new


    # Возвращаем исходные габариты
    xmin = min(p.x for p in pts)
    xmax = max(p.x for p in pts)

    ymin = min(p.y for p in pts)
    ymax = max(p.y for p in pts)


    cx = (
        xmin + xmax
    ) / 2.0

    cy = (
        ymin + ymax
    ) / 2.0


    sx = (
        original_width
        / (xmax - xmin)
    )

    sy = (
        height
        / (ymax - ymin)
    )


    return [

        App.Vector(

            (p.x - cx) * sx,

            (p.y - cy) * sy,

            0

        )

        for p in pts

    ]


# ============================================================
# SMOOTHSTEP
# ============================================================

def smoothstep(v):

    v = max(
        0.0,
        min(
            1.0,
            v
        )
    )

    return (
        v * v
        * (
            3.0
            - 2.0 * v
        )
    )


# ============================================================
# ЛОКАЛЬНАЯ КОРРЕКЦИЯ
# ============================================================

def correction_factor(distance):

    ramp_begin = (
        correction_start
        - correction_ramp
    )

    ramp_end = (
        correction_end
        + correction_ramp
    )


    if distance <= ramp_begin:

        return 0.0


    if distance < correction_start:

        return smoothstep(

            (
                distance
                - ramp_begin
            )

            / correction_ramp

        )


    if distance <= correction_end:

        return 1.0


    if distance < ramp_end:

        return (

            1.0

            - smoothstep(

                (
                    distance
                    - correction_end
                )

                / correction_ramp

            )

        )


    return 0.0


def apply_width_correction(points):

    result = []


    for p in points:

        distance = (

            height / 2.0
            - p.y

        )


        correction = (

            side_correction

            * correction_factor(
                distance
            )

        )


        x = p.x


        if x > 0:

            x = max(
                0,
                x - correction
            )

        elif x < 0:

            x = min(
                0,
                x + correction
            )


        result.append(

            App.Vector(
                x,
                p.y,
                0
            )

        )


    return result


# ============================================================
# ПОВОРОТ В XY
# ============================================================

def rotate_xy(
    x,
    y,
    angle_deg
):

    angle = math.radians(
        angle_deg
    )


    ca = math.cos(angle)
    sa = math.sin(angle)


    return (

        x * ca
        - y * sa,

        x * sa
        + y * ca

    )


# ============================================================
# ПРОФИЛЬ
# ============================================================

base_points = create_base_points()


smooth_points = fair_closed_points(

    base_points,

    fair_passes,

    fair_strength

)


profile_points = apply_width_correction(
    smooth_points
)


# ============================================================
# СОЗДАНИЕ ОДНОГО СЕЧЕНИЯ
#
# progress:
# 0.0 = передняя поверхность
# 1.0 = задняя поверхность
# ============================================================

def make_section(
    points,
    progress
):

    section_points = []


    # --------------------------------------------------------
    # Twist
    # --------------------------------------------------------

    angle = (
        twist_angle_deg
        * progress
    )


    for p in points:

        distance = (
            height / 2.0
            - p.y
        )


        thickness = thickness_at_distance(
            distance
        )


        # ----------------------------------------------------
        # Положение по Z
        #
        # progress 0 -> -T/2
        # progress 1 -> +T/2
        # ----------------------------------------------------

        z = (

            -thickness / 2.0

            + thickness
            * progress

        )


        # ----------------------------------------------------
        # Поворот XY
        # ----------------------------------------------------

        x_rot, y_rot = rotate_xy(

            p.x,
            p.y,
            angle

        )


        section_points.append(

            App.Vector(
                x_rot,
                y_rot,
                z
            )

        )


    spline = Part.BSplineCurve()


    spline.interpolate(

        section_points,

        True

    )


    wire = Part.Wire([

        spline.toShape()

    ])


    if not wire.isClosed():

        raise RuntimeError(
            "Section is not closed"
        )


    if not wire.isValid():

        raise RuntimeError(
            "Section is invalid"
        )


    return wire


# ============================================================
# СОЗДАЕМ ПРОМЕЖУТОЧНЫЕ СЕЧЕНИЯ
# ============================================================

wires = []


for i in range(
    twist_sections
):

    if twist_sections <= 1:

        progress = 0.0

    else:

        progress = (

            i
            / float(
                twist_sections - 1
            )

        )


    wire = make_section(

        profile_points,

        progress

    )


    wires.append(
        wire
    )


# ============================================================
# LOFT
# ============================================================

solid = Part.makeLoft(

    wires,

    True,     # solid

    False     # НЕ ruled — плавная поверхность

)


# ============================================================
# ПРОВЕРКА
# ============================================================

if solid.isNull():

    raise RuntimeError(
        "Solid is null"
    )


if not solid.isValid():

    raise RuntimeError(
        "Solid is invalid"
    )


if (

    len(solid.Solids) != 1

    or

    solid.Volume <= 0

):

    raise RuntimeError(
        "Result must contain one solid"
    )


try:

    solid = solid.removeSplitter()

except Exception:

    pass


# ============================================================
# ДОКУМЕНТ
# ============================================================

doc = App.ActiveDocument


if doc is None:

    doc = App.newDocument(
        "TwistedSpacer"
    )


old = doc.getObject(
    "TwistedSolid"
)


if old:

    doc.removeObject(
        old.Name
    )


obj = doc.addObject(

    "Part::Feature",

    "TwistedSolid"

)


obj.Label = (
    "Twisted parametric spacer"
)


obj.Shape = solid


# ============================================================
# СВОЙСТВА
# ============================================================

properties = [

    (
        "App::PropertyLength",
        "Height",
        height
    ),

    (
        "App::PropertyLength",
        "TopThickness",
        thickness_top
    ),

    (
        "App::PropertyLength",
        "BottomThickness",
        thickness_bottom
    ),

    (
        "App::PropertyAngle",
        "TwistAngle",
        twist_angle_deg
    ),

    (
        "App::PropertyInteger",
        "TwistSections",
        twist_sections
    ),

]


for kind, name, value in properties:

    obj.addProperty(
        kind,
        name,
        "Dimensions"
    )


    setattr(
        obj,
        name,
        value
    )


    obj.setEditorMode(
        name,
        1
    )


obj.ViewObject.ShapeColor = (
    0.78,
    0.80,
    0.84
)


obj.ViewObject.LineColor = (
    0.20,
    0.20,
    0.23
)


doc.recompute()


# ============================================================
# ВИД
# ============================================================

Gui.activeDocument().activeView().viewAxonometric()

Gui.activeDocument().activeView().fitAll()


# ============================================================
# ОТЧЕТ
# ============================================================

App.Console.PrintMessage(

    "\n"
    "====================================\n"
    "TWISTED SOLID CREATED\n"
    "====================================\n"

    "Height: %.2f mm\n"

    "Top thickness: %.2f mm\n"

    "Bottom thickness: %.2f mm\n"

    "Twist angle: %.2f deg\n"

    "Twist sections: %d\n"

    "====================================\n"

    % (

        height,

        thickness_top,

        thickness_bottom,

        twist_angle_deg,

        twist_sections,

    )

)
