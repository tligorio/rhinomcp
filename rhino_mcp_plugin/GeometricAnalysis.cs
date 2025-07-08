using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;
using Newtonsoft.Json.Linq;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin
{
    public static class GeometricAnalysis
    {
        private const double TOLERANCE = 0.01; // Geometric tolerance for analysis

        /// <summary>
        /// Analyzes a geometry object and tries to detect if it's a primitive type
        /// Returns enhanced object info with detected_type and params
        /// </summary>
        public static JObject AnalyzeGeometry(GeometryBase geometry, JObject baseObjectInfo)
        {
            var result = new JObject(baseObjectInfo);
            
            if (geometry is Brep brep)
            {
                var analysis = AnalyzeBrep(brep);
                if (analysis != null)
                {
                    result["detected_type"] = analysis["type"];
                    result["params"] = analysis["params"];
                    result["original_type"] = baseObjectInfo["type"];
                    
                    // Copy additional fields like translation and rotation
                    if (analysis["translation"] != null)
                        result["translation"] = analysis["translation"];
                    if (analysis["rotation"] != null)
                        result["rotation"] = analysis["rotation"];
                }
            }
            else if (geometry is Extrusion extrusion)
            {
                var analysis = AnalyzeExtrusion(extrusion);
                if (analysis != null)
                {
                    result["detected_type"] = analysis["type"];
                    result["params"] = analysis["params"];
                    result["original_type"] = baseObjectInfo["type"];
                    
                    // Copy additional fields like translation and rotation
                    if (analysis["translation"] != null)
                        result["translation"] = analysis["translation"];
                    if (analysis["rotation"] != null)
                        result["rotation"] = analysis["rotation"];
                }
            }
            
            return result;
        }

        /// <summary>
        /// Analyzes a Brep to detect primitive types
        /// </summary>
        private static JObject AnalyzeBrep(Brep brep)
        {
            // Try to detect sphere first
            var sphereResult = TryDetectSphere(brep);
            if (sphereResult != null) return sphereResult;

            // Try to detect cylinder
            var cylinderResult = TryDetectCylinder(brep);
            if (cylinderResult != null) return cylinderResult;

            // Try to detect cone
            var coneResult = TryDetectCone(brep);
            if (coneResult != null) return coneResult;

            // Try to detect box
            var boxResult = TryDetectBox(brep);
            if (boxResult != null) return boxResult;

            return null; // Couldn't detect a primitive type
        }

        /// <summary>
        /// Analyzes an Extrusion to detect primitive types
        /// </summary>
        private static JObject AnalyzeExtrusion(Extrusion extrusion)
        {
            // Check if the profile curve is a circle (cylinder or cone)
            var profile = extrusion.Profile3d(new ComponentIndex(ComponentIndexType.BrepEdge, 0));
            
            if (profile != null)
            {
                // Try to get circle from the profile
                Circle circle;
                if (profile.TryGetCircle(out circle, TOLERANCE))
                {
                                         // This is likely a cylinder
                     var pathLine = new Line(extrusion.PathStart, extrusion.PathEnd);
                     var height = pathLine.Length;
                     var axis = pathLine.Direction;
                    
                    return new JObject
                    {
                        ["type"] = "CYLINDER",
                        ["params"] = new JObject
                        {
                            ["center"] = Serializer.SerializePoint(circle.Center),
                            ["radius"] = Math.Round(circle.Radius, 3),
                            ["height"] = Math.Round(height, 3),
                                                         ["axis"] = Serializer.SerializePoint(new Point3d(axis))
                        }
                    };
                }

                                 // Check if it's rectangular for box detection
                 if (profile.IsClosed && profile.IsPolyline())
                 {
                     Polyline polyline;
                     if (profile.TryGetPolyline(out polyline) && polyline.Count == 5) // Rectangle has 5 points (closed)
                     {
                         var pathLine = new Line(extrusion.PathStart, extrusion.PathEnd);
                         var height = pathLine.Length;
                         
                         // Calculate dimensions from polyline
                         var side1 = polyline[0].DistanceTo(polyline[1]);
                         var side2 = polyline[1].DistanceTo(polyline[2]);
                         var center = extrusion.PathStart + (extrusion.PathEnd - extrusion.PathStart) * 0.5;
                         
                         return new JObject
                         {
                             ["type"] = "BOX",
                             ["params"] = new JObject
                             {
                                 ["center"] = Serializer.SerializePoint(center),
                                 ["width"] = Math.Round(side1, 3),
                                 ["length"] = Math.Round(side2, 3),
                                 ["height"] = Math.Round(height, 3)
                             }
                         };
                     }
                 }
            }

            return null;
        }

        /// <summary>
        /// Try to detect if a Brep is a sphere
        /// </summary>
        private static JObject TryDetectSphere(Brep brep)
        {
            if (brep.Faces.Count == 1)
            {
                var face = brep.Faces[0];
                if (face.IsSphere(TOLERANCE))
                {
                    Sphere sphere;
                    if (face.TryGetSphere(out sphere, TOLERANCE))
                    {
                        return new JObject
                        {
                            ["type"] = "SPHERE",
                            ["params"] = new JObject
                            {
                                ["center"] = Serializer.SerializePoint(sphere.Center),
                                ["radius"] = Math.Round(sphere.Radius, 3)
                            }
                        };
                    }
                }
            }
            return null;
        }

        /// <summary>
        /// Try to detect if a Brep is a cylinder
        /// </summary>
        private static JObject TryDetectCylinder(Brep brep)
        {
            if (brep.Faces.Count == 3) // 2 caps + 1 cylindrical surface
            {
                BrepFace cylindricalFace = null;
                var capFaces = new List<BrepFace>();

                foreach (var face in brep.Faces)
                {
                    if (face.IsCylinder(TOLERANCE))
                    {
                        cylindricalFace = face;
                    }
                    else
                    {
                        capFaces.Add(face);
                    }
                }

                if (cylindricalFace != null && capFaces.Count == 2)
                {
                    Cylinder cylinder;
                    if (cylindricalFace.TryGetCylinder(out cylinder, TOLERANCE))
                    {
                        // Calculate rotation from axis
                        var rotation = CalculateRotationFromAxis(cylinder.Axis);
                        
                        var result = new JObject
                        {
                            ["type"] = "CYLINDER",
                            ["params"] = new JObject
                            {
                                ["radius"] = Math.Round(cylinder.Radius, 3),
                                ["height"] = Math.Round(cylinder.TotalHeight, 3),
                                ["cap"] = true
                            }
                        };
                        
                        // Add center as translation
                        result["translation"] = Serializer.SerializePoint(cylinder.Center);
                        
                        // Add rotation if needed (non-default orientation)
                        if (rotation != null)
                        {
                            result["rotation"] = rotation;
                        }
                        
                        return result;
                    }
                }
            }
            return null;
        }

        /// <summary>
        /// Try to detect if a Brep is a cone
        /// </summary>
        private static JObject TryDetectCone(Brep brep)
        {
            if (brep.Faces.Count == 2) // 1 cap + 1 conical surface
            {
                BrepFace conicalFace = null;
                BrepFace capFace = null;

                foreach (var face in brep.Faces)
                {
                    if (face.IsCone(TOLERANCE))
                    {
                        conicalFace = face;
                    }
                    else
                    {
                        capFace = face;
                    }
                }

                if (conicalFace != null && capFace != null)
                {
                    Cone cone;
                    if (conicalFace.TryGetCone(out cone, TOLERANCE))
                    {
                        // Use bounding box to find the actual base center
                        var bbox = brep.GetBoundingBox(true);
                        var apexPoint = cone.ApexPoint;
                        
                        // Calculate base center for translation (where the base should be positioned)
                        var baseCenterPoint = new Point3d(
                            (bbox.Min.X + bbox.Max.X) / 2,  // Center X
                            (bbox.Min.Y + bbox.Max.Y) / 2,  // Center Y
                            bbox.Min.Z                      // Bottom Z (base level)
                        );
                        
                        // Calculate axis from base to apex for rotation
                        var baseToApexAxis = apexPoint - baseCenterPoint;
                        baseToApexAxis.Unitize();
                        
                        // Calculate rotation from detected axis to Claude's expected axis
                        var rotation = CalculateRotationFromAxis(baseToApexAxis);
                        
                        var result = new JObject
                        {
                            ["type"] = "CONE",
                            ["params"] = new JObject
                            {
                                ["radius"] = Math.Round(cone.Radius, 3),
                                ["height"] = Math.Round(cone.Height, 3),
                                ["cap"] = true
                            }
                        };
                        
                        // Add base center as translation
                        result["translation"] = Serializer.SerializePoint(baseCenterPoint);
                        
                        // Add rotation if needed (non-default orientation)
                        if (rotation != null)
                        {
                            result["rotation"] = rotation;
                        }
                        
                        return result;
                    }
                }
            }
            return null;
        }

        /// <summary>
        /// Calculate rotation angles needed to orient an object from default [0,0,1] axis to target axis
        /// Returns null if no rotation needed (axis is already [0,0,1])
        /// </summary>
        private static JArray CalculateRotationFromAxis(Vector3d targetAxis)
        {
            var defaultAxis = Vector3d.ZAxis; // [0, 0, 1] - default upward direction
            
            // Normalize the target axis
            targetAxis.Unitize();
            
            // If already pointing up, no rotation needed
            if (targetAxis.IsParallelTo(defaultAxis, TOLERANCE) == 1)
            {
                return null;
            }
            
            // If pointing straight down, rotate 180° around X-axis
            if (targetAxis.IsParallelTo(-defaultAxis, TOLERANCE) == 1)
            {
                return new JArray { Math.PI, 0.0, 0.0 }; // 180° around X-axis
            }
            
            // For other orientations, calculate the rotation
            // This is a simplified approach - for complex orientations, more sophisticated calculation needed
            var cross = Vector3d.CrossProduct(defaultAxis, targetAxis);
            var angle = Vector3d.VectorAngle(defaultAxis, targetAxis);
            
            if (cross.Length > TOLERANCE)
            {
                cross.Unitize();
                
                // Convert axis-angle to Euler angles (simplified)
                // For now, handle common cases
                if (Math.Abs(cross.X) > 0.9) // Rotation around X-axis
                {
                    return new JArray { angle, 0.0, 0.0 };
                }
                else if (Math.Abs(cross.Y) > 0.9) // Rotation around Y-axis
                {
                    return new JArray { 0.0, angle, 0.0 };
                }
                else // Default to rotation around X-axis
                {
                    return new JArray { angle, 0.0, 0.0 };
                }
            }
            
            return null; // No rotation needed
        }

        /// <summary>
        /// Try to detect if a Brep is a box
        /// </summary>
        private static JObject TryDetectBox(Brep brep)
        {
            if (brep.Faces.Count == 6) // 6 faces for a box
            {
                var bbox = brep.GetBoundingBox(true);
                
                // Check if it's roughly a box by analyzing faces
                var faceNormals = brep.Faces.Select(f => f.NormalAt(f.Domain(0).Mid, f.Domain(1).Mid)).ToArray();
                
                // A box should have faces with normals pointing in 6 cardinal directions
                var cardinalDirections = new[] { Vector3d.XAxis, -Vector3d.XAxis, Vector3d.YAxis, -Vector3d.YAxis, Vector3d.ZAxis, -Vector3d.ZAxis };
                
                int matchingDirections = 0;
                foreach (var normal in faceNormals)
                {
                    if (cardinalDirections.Any(dir => normal.IsParallelTo(dir, TOLERANCE) != 0))
                    {
                        matchingDirections++;
                    }
                }

                if (matchingDirections >= 4) // Allow some tolerance
                {
                    var dimensions = bbox.Max - bbox.Min;
                    var center = bbox.Center;

                    return new JObject
                    {
                        ["type"] = "BOX",
                        ["params"] = new JObject
                        {
                            ["center"] = Serializer.SerializePoint(center),
                            ["width"] = Math.Round(dimensions.X, 3),
                            ["length"] = Math.Round(dimensions.Y, 3),
                            ["height"] = Math.Round(dimensions.Z, 3)
                        }
                    };
                }
            }
            return null;
        }
    }
}