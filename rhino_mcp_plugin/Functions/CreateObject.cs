using System;
using System.Collections.Generic;
using System.Drawing;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject CreateObject(JObject parameters)
    {
        // parse meta data
        string type = castToString(parameters.SelectToken("type"));
        string name = castToString(parameters.SelectToken("name"));
        bool customColor = parameters.ContainsKey("color");
        int[] color = castToIntArray(parameters.SelectToken("color"));
        JObject geoParams = (JObject)parameters.SelectToken("params");

        var doc = RhinoDoc.ActiveDoc;
        Guid objectId = Guid.Empty;

        // Create a box centered at the specified point
        switch (type)
        {
            case "POINT":
                double x = castToDouble(geoParams.SelectToken("x"));
                double y = castToDouble(geoParams.SelectToken("y"));
                double z = castToDouble(geoParams.SelectToken("z"));
                objectId = doc.Objects.AddPoint(x, y, z);
                break;
            case "LINE":
                double[] start = castToDoubleArray(geoParams.SelectToken("start"));
                double[] end = castToDoubleArray(geoParams.SelectToken("end"));
                var ptStart = new Point3d(start[0], start[1], start[2]);
                var ptEnd = new Point3d(end[0], end[1], end[2]);
                objectId = doc.Objects.AddLine(ptStart, ptEnd);
                break;
            case "POLYLINE":
                List<Point3d> ptList = castToPoint3dList(geoParams.SelectToken("points"));
                objectId = doc.Objects.AddPolyline(ptList);
                break;
            case "CIRCLE":
                Point3d circleCenter = castToPoint3d(geoParams.SelectToken("center"));
                double circleRadius = castToDouble(geoParams.SelectToken("radius"));
                var circle = new Circle(circleCenter, circleRadius);
                objectId = doc.Objects.AddCircle(circle);
                break;
            case "ARC":
                Point3d arcCenter = castToPoint3d(geoParams.SelectToken("center"));
                double arcRadius = castToDouble(geoParams.SelectToken("radius"));
                double arcAngle = castToDouble(geoParams.SelectToken("angle"));
                var arc = new Arc(new Plane(arcCenter, Vector3d.ZAxis), arcRadius, arcAngle * Math.PI / 180);
                objectId = doc.Objects.AddArc(arc);
                break;
            case "ELLIPSE":
                Point3d ellipseCenter = castToPoint3d(geoParams.SelectToken("center"));
                double ellipseRadiusX = castToDouble(geoParams.SelectToken("radius_x"));
                double ellipseRadiusY = castToDouble(geoParams.SelectToken("radius_y"));
                var ellipse = new Ellipse(new Plane(ellipseCenter, Vector3d.ZAxis), ellipseRadiusX, ellipseRadiusY);
                objectId = doc.Objects.AddEllipse(ellipse);
                break;
            case "CURVE":
                List<Point3d> controlPoints = castToPoint3dList(geoParams.SelectToken("points"));
                int degree = castToInt(geoParams.SelectToken("degree"));
                var curve = Curve.CreateControlPointCurve(controlPoints, degree) ?? throw new InvalidOperationException("unable to create control point curve from given points");
                objectId = doc.Objects.AddCurve(curve);
                break;
            case "BOX":
                // parse size
                double width = castToDouble(geoParams.SelectToken("width"));
                double length = castToDouble(geoParams.SelectToken("length"));
                double height = castToDouble(geoParams.SelectToken("height"));
                double xSize = width, ySize = length, zSize = height;
                Box box = new Box(
                    Plane.WorldXY,
                    new Interval(-xSize / 2, xSize / 2),
                    new Interval(-ySize / 2, ySize / 2),
                    new Interval(-zSize / 2, zSize / 2)
                );
                objectId = doc.Objects.AddBox(box);
                break;

            case "SPHERE":
                // parse radius
                double radius = castToDouble(geoParams.SelectToken("radius"));
                // Create sphere at origin with specified radius
                Sphere sphere = new Sphere(Point3d.Origin, radius);
                // Convert sphere to BREP for adding to document
                objectId = doc.Objects.AddBrep(sphere.ToBrep());
                break;
            case "CONE":
                double coneRadius = castToDouble(geoParams.SelectToken("radius"));
                double coneHeight = castToDouble(geoParams.SelectToken("height"));
                bool coneCap = castToBool(geoParams.SelectToken("cap"));
                
                // Create UPWARD pointing cone with BASE CENTER at origin (for proper translation)
                // RhinoCommon puts apex at plane origin, base at plane_origin + height * plane_normal
                // For base at origin and apex above: plane_origin + height * plane_normal = origin
                // So: plane_origin = -height * plane_normal
                // For upward cone: plane_normal = (0,0,-1), so plane_origin = (0,0,height)
                var baseCenterPlane = new Plane(new Point3d(0, 0, coneHeight), -Vector3d.ZAxis);
                Cone cone = new Cone(baseCenterPlane, coneHeight, coneRadius);
                
                // DEBUG: Verify the fix
                RhinoApp.WriteLine($"=== FIXED CONE CREATION DEBUG ===");
                RhinoApp.WriteLine($"Requested: radius={coneRadius}, height={coneHeight}");
                RhinoApp.WriteLine($"Fixed Cone.ApexPoint: {cone.ApexPoint}");
                RhinoApp.WriteLine($"Fixed Cone.BasePoint: {cone.BasePoint}");
                if (cone.ApexPoint.Z > cone.BasePoint.Z)
                    RhinoApp.WriteLine("FIXED: Creates UPWARD pointing cone");
                else if (cone.ApexPoint.Z < cone.BasePoint.Z)  
                    RhinoApp.WriteLine("FIXED: Creates DOWNWARD pointing cone");
                else
                    RhinoApp.WriteLine("FIXED: Creates HORIZONTAL cone");
                
                Brep brep = Brep.CreateFromCone(cone, coneCap);
                var bbox = brep.GetBoundingBox(true);
                RhinoApp.WriteLine($"Fixed Pre-translation BoundingBox: {bbox.Min} to {bbox.Max}");
                objectId = doc.Objects.AddBrep(brep);
                RhinoApp.WriteLine($"=== END FIXED CONE DEBUG ===");
                break;
            case "CYLINDER":
                double cylinderRadius = castToDouble(geoParams.SelectToken("radius"));
                double cylinderHeight = castToDouble(geoParams.SelectToken("height"));
                bool cylinderCap = castToBool(geoParams.SelectToken("cap"));
                Circle cylinderCircle = new Circle(Plane.WorldXY, cylinderRadius);
                Cylinder cylinder = new Cylinder(cylinderCircle, cylinderHeight);
                objectId = doc.Objects.AddBrep(cylinder.ToBrep(cylinderCap, cylinderCap));
                break;
            case "SURFACE":
                int[] surfaceCount = castToIntArray(geoParams.SelectToken("count"));
                List<Point3d> surfacePoints = castToPoint3dList(geoParams.SelectToken("points"));
                int[] surfaceDegree = castToIntArray(geoParams.SelectToken("degree"));
                bool[] surfaceClosed = castToBoolArray(geoParams.SelectToken("closed"));
                var surf = NurbsSurface.CreateThroughPoints(surfacePoints, surfaceCount[0], surfaceCount[1], surfaceDegree[0], surfaceDegree[1], surfaceClosed[0], surfaceClosed[1]);
                objectId = doc.Objects.AddSurface(surf);
                break;
            default:
                throw new InvalidOperationException("Invalid object type");
        }

        if (objectId == Guid.Empty)
            throw new InvalidOperationException("Failed to create object");

        var rhinoObject = doc.Objects.Find(objectId);
        if (rhinoObject != null)
        {
            if (!string.IsNullOrEmpty(name)) rhinoObject.Attributes.Name = name;
            if (customColor)
            {
                rhinoObject.Attributes.ColorSource = ObjectColorSource.ColorFromObject;
                rhinoObject.Attributes.ObjectColor = Color.FromArgb(color[0], color[1], color[2]);
            }
            doc.Objects.ModifyAttributes(rhinoObject, rhinoObject.Attributes, true);

            var geometry = rhinoObject.Geometry;
            var xform = Transform.Identity;
            bool geometryModified = false;

            // Change translation if provided
            if (parameters["translation"] != null)
            {
                xform *= applyTranslation(parameters);
                geometryModified = true;
            }

            // Apply scale if provided
            if (parameters["scale"] != null)
            {
                xform *= applyScale(parameters, geometry);
                geometryModified = true;
            }

            // Apply rotation if provided
            if (parameters["rotation"] != null)
            {
                xform *= applyRotation(parameters, geometry);
                geometryModified = true;
            }

            if (geometryModified)
            {
                doc.Objects.Transform(rhinoObject, xform, true);
            }
        }

        // Update views
        doc.Views.Redraw();

        return Serializer.RhinoObject(doc.Objects.Find(objectId));
    }
}