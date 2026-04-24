mkdir SectionAutoBlock
cd SectionAutoBlock
dotnet new classlib --framework net47 -n SectionAutoBlock
cd SectionAutoBlock



<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net47</TargetFramework>
    <Nullable>disable</Nullable>
    <PlatformTarget>x64</PlatformTarget>
  </PropertyGroup>

  <ItemGroup>
    <Reference Include="acdbmgd">
      <HintPath>C:\Program Files\Autodesk\AutoCAD 2018\acdbmgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="acmgd">
      <HintPath>C:\Program Files\Autodesk\AutoCAD 2018\acmgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="AcCoreMgd">
      <HintPath>C:\Program Files\Autodesk\AutoCAD 2018\AcCoreMgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
  </ItemGroup>

</Project>