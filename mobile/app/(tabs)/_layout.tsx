import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { Image, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useColors } from '../../src/theme-context';

function PetLensHeader() {
  const colors = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
      <Image
        accessibilityLabel="PetLens analysis for dogs"
        source={require('../../assets/petlens-dog-mark.png')}
        style={{ width: 42, height: 42, borderRadius: 13, backgroundColor: '#fff' }}
      />
      <View>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: '800' }}>PetLens</Text>
        <Text style={{ color: colors.muted, fontSize: 9, letterSpacing: 1.1 }}>ANALYSIS FOR DOGS</Text>
      </View>
    </View>
  );
}

export default function TabsLayout() {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        headerTitle: PetLensHeader,
        headerRight: () => (
          <Text style={{ color: colors.muted, fontSize: 11, fontWeight: '700', letterSpacing: 1.1 }}>
            BETA
          </Text>
        ),
        tabBarActiveTintColor: '#ffffff',
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '700' },
        tabBarItemStyle: { borderRadius: 12, marginHorizontal: 3, marginVertical: 1 },
        tabBarActiveBackgroundColor: 'rgba(55,148,164,0.2)',
        // Leave room for Android's gesture area below the floating tabs.
        tabBarStyle: {
          position: 'absolute',
          left: 15,
          right: 15,
          bottom: Math.max(12, insets.bottom + 8),
          height: 90,
          minHeight: 90,
          backgroundColor: 'rgba(6,24,38,0.96)',
          borderTopWidth: 1,
          borderWidth: 1,
          borderColor: 'rgba(22,105,170,0.4)',
          borderRadius: 18,
          paddingTop: 7,
          paddingBottom: 7,
          shadowColor: '#000000',
          shadowOpacity: 0.3,
          shadowRadius: 14,
          shadowOffset: { width: 0, height: 8 },
          elevation: 12,
        },
        sceneStyle: { backgroundColor: colors.background, paddingBottom: 112 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Overview',
          tabBarIcon: ({ color, size }) => <Ionicons name="pulse-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="analyze"
        options={{
          title: 'New analysis',
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <Ionicons name="time-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="pet/index"
        options={{
          title: 'Pet profile',
          tabBarIcon: ({ color, size }) => <Ionicons name="paw-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
