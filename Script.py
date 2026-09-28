import FreeCAD as App
import FreeCADGui as Gui
import Part
import math


# ============================================================
# ОСНОВНЫЕ ПАРАМЕТРЫ, мм
# ============================================================

height = 126.5


# ============================================================
# ТОЛЩИНА КЛИНА
#
# Верх: 30 мм
# Низ:  10 мм
#
# Толщина распределяется СИММЕТРИЧНО относительно Z = 0:
#
# верх:   -15 ... +15
# низ:     -5 ...  +5
#
# ============================================================

thickness_top = 35.0
thickness_bottom = 15.0


# ============================================================
# ОТВЕРСТИЯ
# ============================================================

hole_diameter = 5.0

# центр первого отверстия от верхней точки
hole1_from_top = 20.0

# расстояние между центрами
hole_spacing = 80.0


# ============================================================
# СГЛАЖИВАНИЕ КОНТУРА
# ============================================================

samples_per_segment = 48

fair_passes = 8

fair_strength = 0.22


# ============================================================
# КОРРЕКЦИЯ ШИРИНЫ
#
# Убираем 0.35 мм С КАЖДОЙ стороны.
#
# Основная область:
# 20...70 мм от верха
#
# Переход делаем плавным на 5 мм.
# ============================================================

side_correction = 0.20

correction_start = 10.0
correction_end = 120.0

correction_ramp = 5.0


# ============================================================
# ИСХОДНЫЕ ЗАМЕРЫ
#
# (расстояние от верха, полная ширина)
# ============================================================

measurements = [

    (10.0, 29.0),

    (20.0, 36.0),

    (30.0, 41.0),

    (40.0, 42.5),

    (50.0, 42.5),

    (60.0, 42.0),

    (80.0, 40.0),

    (100.0, 34.0),

    (110.0, 29.0),

    (120.0, 20.0),

]


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
# УГОЛ КЛИНА
# ============================================================

total_delta = (
    thickness_top
    - thickness_bottom
)


total_angle_deg = math.degrees(

    math.atan2(
        total_delta,
        height
    )

)


# Поскольку угол распределяем на ДВЕ стороны,
# наклон каждой поверхности вдвое меньше по Z.

surface_angle_deg = math.degrees(

    math.atan2(
        total_delta / 2.0,
        height
    )

)


# ============================================================
# ФУНКЦИЯ ТОЛЩИНЫ
#
# distance = расстояние от верха.
#
# 0 мм       -> 30 мм
# height     -> 10 мм
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

        x[i + 1]
        - x[i]

        for i in range(
            count - 1
        )

    ]


    sec = [

        (
            values[i + 1]
            - values[i]
        )
        / h[i]

        for i in range(
            count - 1
        )

    ]


    slopes = [
        0.0
    ] * count


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

            return (
                3.0 * d0
            )


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


        if before * after <= 0.0:

            slopes[i] = 0.0


        else:

            weight1 = (
                2.0 * h[i]
                + h[i - 1]
            )


            weight2 = (
                h[i]
                + 2.0 * h[i - 1]
            )


            slopes[i] = (

                weight1
                + weight2

            ) / (

                weight1 / before
                + weight2 / after

            )


    return slopes


slopes = monotone_slopes(
    depths,
    radii
)


# ============================================================
# КУБИЧЕСКИЕ СЕГМЕНТЫ
# ============================================================

segments = []


first_depth = depths[0]

first_radius = radii[0]

handle_depth = (
    first_depth / 3.0
)


# Верхнее закругление
segments.append([

    (
        0.0,
        0.0
    ),

    (
        first_radius * 0.55,
        0.0
    ),

    (

        first_radius
        - slopes[0]
        * handle_depth,

        first_depth
        - handle_depth

    ),

    (
        first_radius,
        first_depth
    ),

])


# Основные участки
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
            + slopes[i]
            * step / 3.0,

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
# БАЗОВЫЕ ТОЧКИ КОНТУРА
# ============================================================

def create_base_points():

    smooth_segments = [

        list(poles)
        for poles in segments

    ]


    # Более плавный низ
    smooth_segments[-1][-2] = (

        4.0,
        height

    )


    all_segments = list(
        smooth_segments
    )


    # Левая сторона зеркально
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


            u = (
                1.0 - t
            )


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
                    0.0
                )

            )


    return points


# ============================================================
# FAIRING — СГЛАЖИВАНИЕ
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
            0.0
        )

        for p in points

    ]


    for _ in range(
        passes
    ):

        old = pts

        new = []

        count = len(old)


        for i in range(
            count
        ):

            previous = old[
                (i - 1) % count
            ]

            current = old[i]

            following = old[
                (i + 1) % count
            ]


            average_x = (

                previous.x
                + following.x

            ) / 2.0


            average_y = (

                previous.y
                + following.y

            ) / 2.0


            x = (

                current.x
                * (1.0 - strength)

                + average_x
                * strength

            )


            y = (

                current.y
                * (1.0 - strength)

                + average_y
                * strength

            )


            new.append(

                App.Vector(
                    x,
                    y,
                    0.0
                )

            )


        pts = new


    # ========================================================
    # Возвращаем исходные габариты
    # ========================================================

    xmin = min(
        p.x
        for p in pts
    )

    xmax = max(
        p.x
        for p in pts
    )

    ymin = min(
        p.y
        for p in pts
    )

    ymax = max(
        p.y
        for p in pts
    )


    current_width = (
        xmax - xmin
    )

    current_height = (
        ymax - ymin
    )


    cx = (
        xmin + xmax
    ) / 2.0


    cy = (
        ymin + ymax
    ) / 2.0


    sx = (

        original_width
        / current_width

    )


    sy = (

        height
        / current_height

    )


    result = []


    for p in pts:

        result.append(

            App.Vector(

                (
                    p.x - cx
                ) * sx,

                (
                    p.y - cy
                ) * sy,

                0.0

            )

        )


    return result


# ============================================================
# ПЛАВНАЯ КОРРЕКЦИЯ ШИРИНЫ
# ============================================================

def smoothstep(value):

    value = max(
        0.0,
        min(
            1.0,
            value
        )
    )


    return (

        value
        * value

        * (
            3.0
            - 2.0 * value
        )

    )


def correction_factor(
    distance
):

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


def apply_width_correction(
    points
):

    result = []


    for p in points:

        distance = (

            height / 2.0
            - p.y

        )


        factor = correction_factor(
            distance
        )


        correction = (

            side_correction
            * factor

        )


        x = p.x


        if x > 0.0:

            x = max(

                0.0,

                x
                - correction

            )


        elif x < 0.0:

            x = min(

                0.0,

                x
                + correction

            )


        result.append(

            App.Vector(
                x,
                p.y,
                0.0
            )

        )


    return result


# ============================================================
# СОЗДАЕМ ФИНАЛЬНЫЙ КОНТУР
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
# СОЗДАЕМ ПЕРЕДНИЙ И ЗАДНИЙ КОНТУРЫ
#
# КЛЮЧЕВОЕ ОТЛИЧИЕ:
#
# front = -thickness / 2
# back  = +thickness / 2
#
# Поэтому обе поверхности наклонные,
# а средняя плоскость всегда Z = 0.
# ============================================================

def make_wire(
    points,
    side
):

    curve_points = []


    for p in points:

        distance = (

            height / 2.0
            - p.y

        )


        thickness = thickness_at_distance(
            distance
        )


        if side == "front":

            z = (
                -thickness / 2.0
            )

        elif side == "back":

            z = (
                thickness / 2.0
            )

        else:

            raise ValueError(
                "side must be front or back"
            )


        curve_points.append(

            App.Vector(
                p.x,
                p.y,
                z
            )

        )


    spline = Part.BSplineCurve()


    spline.interpolate(

        curve_points,

        True

    )


    wire = Part.Wire([

        spline.toShape()

    ])


    if not wire.isClosed():

        raise RuntimeError(
            "Контур не замкнут"
        )


    if not wire.isValid():

        raise RuntimeError(
            "Контур некорректен"
        )


    return wire


front_wire = make_wire(
    profile_points,
    "front"
)


back_wire = make_wire(
    profile_points,
    "back"
)


# ============================================================
# СОЗДАЕМ SOLID
# ============================================================

solid = Part.makeLoft(

    [
        front_wire,
        back_wire
    ],

    True,

    True

)


if solid.isNull():

    raise RuntimeError(
        "Solid пуст"
    )


if not solid.isValid():

    raise RuntimeError(
        "Solid некорректен"
    )


if (

    len(solid.Solids) != 1

    or

    solid.Volume <= 0

):

    raise RuntimeError(
        "Результат должен содержать одно твердое тело"
    )


# ============================================================
# ОТВЕРСТИЯ
# ============================================================

hole_radius = (

    hole_diameter
    / 2.0

)


top_y = (

    height
    / 2.0

)


hole1_y = (

    top_y
    - hole1_from_top

)


hole2_y = (

    hole1_y
    - hole_spacing

)


# Режущий цилиндр должен пройти насквозь
# от отрицательной до положительной стороны Z.

cut_margin = 5.0


max_half_thickness = (

    max(
        thickness_top,
        thickness_bottom
    )

    / 2.0

)


cylinder_start_z = (

    -max_half_thickness
    - cut_margin

)


cylinder_height = (

    2.0
    * max_half_thickness

    + 2.0
    * cut_margin

)


hole1 = Part.makeCylinder(

    hole_radius,

    cylinder_height,

    App.Vector(

        0.0,

        hole1_y,

        cylinder_start_z

    ),

    App.Vector(
        0,
        0,
        1
    )

)


hole2 = Part.makeCylinder(

    hole_radius,

    cylinder_height,

    App.Vector(

        0.0,

        hole2_y,

        cylinder_start_z

    ),

    App.Vector(
        0,
        0,
        1
    )

)


solid = solid.cut(
    hole1
)


solid = solid.cut(
    hole2
)


try:

    solid = solid.removeSplitter()

except Exception:

    pass


# ============================================================
# ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================

if solid.isNull():

    raise RuntimeError(
        "Финальный Solid пуст"
    )


if not solid.isValid():

    raise RuntimeError(
        "Финальный Solid некорректен"
    )


# ============================================================
# FREECAD DOCUMENT
# ============================================================

doc = App.ActiveDocument


if doc is None:

    doc = App.newDocument(
        "CenteredWedge"
    )


doc.openTransaction(
    "Create centered wedge"
)


try:

    old = doc.getObject(
        "WedgeSolid"
    )


    if old:

        doc.removeObject(
            old.Name
        )


    obj = doc.addObject(

        "Part::Feature",

        "WedgeSolid"

    )


    obj.Label = (
        "Centered wedge 30-10 mm"
    )


    obj.Shape = solid


    # ========================================================
    # ПАРАМЕТРЫ В СВОЙСТВАХ
    # ========================================================

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
            "TotalWedgeAngle",
            total_angle_deg
        ),

        (
            "App::PropertyAngle",
            "SurfaceAngle",
            surface_angle_deg
        ),

        (
            "App::PropertyLength",
            "SideCorrection",
            side_correction
        ),

        (
            "App::PropertyLength",
            "HoleDiameter",
            hole_diameter
        ),

        (
            "App::PropertyLength",
            "Hole1FromTop",
            hole1_from_top
        ),

        (
            "App::PropertyLength",
            "HoleSpacing",
            hole_spacing
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


    doc.commitTransaction()


except Exception:

    doc.abortTransaction()

    raise


# ============================================================
# ВИД
# ============================================================

Gui.activeDocument().activeView().viewAxonometric()


Gui.activeDocument().activeView().fitAll()


# ============================================================
# ОТЧЕТ
# ============================================================

middle_thickness = thickness_at_distance(
    height / 2.0
)


App.Console.PrintMessage(

    "\n"
    "========================================\n"
    "CENTERED WEDGE CREATED\n"
    "========================================\n"

    "Height: %.2f mm\n"

    "\n"

    "Top thickness: %.2f mm\n"

    "Middle thickness: %.2f mm\n"

    "Bottom thickness: %.2f mm\n"

    "\n"

    "Top surfaces: Z = +/- %.2f mm\n"

    "Middle surfaces: Z = +/- %.2f mm\n"

    "Bottom surfaces: Z = +/- %.2f mm\n"

    "\n"

    "Total wedge angle: %.3f deg\n"

    "Angle of each surface: %.3f deg\n"

    "\n"

    "Side correction: %.2f mm\n"

    "Correction zone: %.1f - %.1f mm\n"

    "\n"

    "Hole diameter: %.2f mm\n"

    "Hole 1 from top: %.2f mm\n"

    "Hole spacing: %.2f mm\n"

    "========================================\n"

    % (

        height,

        thickness_top,

        middle_thickness,

        thickness_bottom,

        thickness_top / 2.0,

        middle_thickness / 2.0,

        thickness_bottom / 2.0,

        total_angle_deg,

        surface_angle_deg,

        side_correction,

        correction_start,

        correction_end,

        hole_diameter,

        hole1_from_top,

        hole_spacing,

    )

)
